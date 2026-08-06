"""
Verificación E2E de maestros y upserts BD v2 (F-05).

Portales mockeados; Postgres real (Supabase local). Omite la suite si no hay BD.
Criterios: docs/DB_DESIGN_V2.md §12 · docs/VALIDACION_MAESTROS_UPSERT.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator, Optional
from uuid import UUID, uuid4

import pytest

from config.settings import Settings, clear_settings_cache, get_settings
from controllers.persistencia_post_consulta import intentar_persistir_resultado
from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import (
    ComparendoMulta,
    ResultadoSimit,
    ResumenSimit,
)
from repositories import ConsultaRepository, get_database, reset_database
from repositories.exceptions import ConexionPersistenciaError, PersistenciaError

_COLUMNAS_ELEGIBILIDAD_PROHIBIDAS = (
    "apto",
    "puede_tramitar",
    "elegible",
    "elegibilidad",
    "dictamen",
)

_TABLAS_APP_V2 = (
    "consultas",
    "resultados_runt",
    "resultados_simit",
    "eventos_consulta",
    "personas",
    "vehiculos",
    "persona_vehiculo",
    "licencias",
    "infracciones_runt",
    "obligaciones_simit",
    "acuerdos_pago_simit",
)


def _db_disponible() -> bool:
    clear_settings_cache()
    reset_database()
    settings = get_settings()
    if not settings.database_url:
        return False
    try:
        return get_database(settings).ping()
    except (PersistenciaError, ConexionPersistenciaError):
        return False


pytestmark = pytest.mark.skipif(
    not _db_disponible(),
    reason="Postgres Supabase local no disponible (DATABASE_URL / Docker)",
)


@pytest.fixture
def repo() -> Iterator[ConsultaRepository]:
    clear_settings_cache()
    reset_database()
    yield ConsultaRepository(get_database())


def _settings_ok(**overrides: Any) -> Settings:
    base = get_settings()
    data = {
        "app_env": base.app_env,
        "debug": base.debug,
        "log_level": base.log_level,
        "log_file": base.log_file,
        "runt_url": base.runt_url,
        "simit_url": base.simit_url,
        "browser_headless": base.browser_headless,
        "runt_slow_mo_ms": base.runt_slow_mo_ms,
        "simit_slow_mo_ms": base.simit_slow_mo_ms,
        "navigation_timeout_ms": base.navigation_timeout_ms,
        "runt_network_idle_timeout_ms": base.runt_network_idle_timeout_ms,
        "simit_network_idle_timeout_ms": base.simit_network_idle_timeout_ms,
        "simit_results_timeout_ms": base.simit_results_timeout_ms,
        "runt_captcha_timeout_ms": base.runt_captcha_timeout_ms,
        "database_url": base.database_url,
        "db_connect_timeout_s": base.db_connect_timeout_s,
        "persistencia_enabled": True,
        "operador": "f05",
        "estacion": "pytest-maestros",
        "app_version": "f05",
        "supabase_url": base.supabase_url,
        "supabase_anon_key": base.supabase_anon_key,
        "supabase_service_role_key": base.supabase_service_role_key,
    }
    data.update(overrides)
    return Settings(**data)


def _count(repo: ConsultaRepository, sql: str, params: Optional[dict] = None) -> int:
    with repo._db.connection() as conn:
        row = conn.execute(sql, params or {}).fetchone()
    assert row is not None
    return int(row["n"])


def _assert_sin_elegibilidad_esquema_v2(repo: ConsultaRepository) -> None:
    with repo._db.connection() as conn:
        rows = conn.execute(
            """
            select table_name, column_name
              from information_schema.columns
             where table_schema = 'public'
               and table_name = any(%(tablas)s)
            """,
            {"tablas": list(_TABLAS_APP_V2)},
        ).fetchall()
    nombres = {str(r["column_name"]).lower() for r in rows}
    prohibidas = [c for c in _COLUMNAS_ELEGIBILIDAD_PROHIBIDAS if c in nombres]
    assert not prohibidas, f"Columnas de elegibilidad encontradas: {prohibidas}"
    tablas = {str(r["table_name"]) for r in rows}
    for t in ("personas", "vehiculos", "obligaciones_simit"):
        assert t in tablas, f"Falta tabla v2 {t} (¿migraciones F-01 aplicadas?)"


def _persistir(repo: ConsultaRepository, resultado: ResultadoConsulta) -> UUID:
    intentar_persistir_resultado(
        resultado,
        settings=_settings_ok(),
        repository=repo,
    )
    assert resultado.persistido is True
    assert isinstance(resultado.consulta_db_id, UUID)
    return resultado.consulta_db_id


def _numero_documento_unico(prefijo: str = "805") -> str:
    """Identificador numérico único (evita divergencia por upper() del normalizador)."""
    return f"{prefijo}{uuid4().int % 10_000_000:07d}"


def _placa_unica(prefijo: str = "ZZ") -> str:
    return f"{prefijo}{uuid4().int % 10_000:04d}"


def test_f05_01_dos_documentos_una_persona(repo: ConsultaRepository) -> None:
    """§12.1: 2 consultas misma CC → 1 personas."""
    _assert_sin_elegibilidad_esquema_v2(repo)
    numero = _numero_documento_unico("805")
    for i in range(2):
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador=numero,
            tipo_documento="CC",
            correlation_id=f"f05-doc-{i}-{numero}",
            iniciado_en=datetime.now(timezone.utc),
            resultado_runt=ResultadoRunt(
                nombre=f"Persona F05 {i}",
                tipo_documento="CC",
                numero_documento=numero,
                estado_persona="ACTIVO",
                secciones={
                    "LICENCIAS": [
                        {"NÚMERO": f"LIC-{numero}", "CATEGORÍA": "B1", "ESTADO": "ACTIVA"}
                    ]
                },
                raw_html=f"<runt-f05-{i}/>",
            ),
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador=numero,
                    modo="DOCUMENTO",
                    sin_pendientes=True,
                ),
                raw_html=f"<simit-f05-{i}/>",
            ),
        )
        r.finalizar()
        _persistir(repo, r)

    n_consultas = _count(
        repo,
        """
        select count(*) as n from public.consultas
         where modo = 'DOCUMENTO' and identificador = %(id)s
        """,
        {"id": numero},
    )
    n_personas = _count(
        repo,
        """
        select count(*) as n from public.personas
         where tipo_documento = 'CC' and numero_documento = %(id)s
        """,
        {"id": numero},
    )
    n_licencias = _count(
        repo,
        """
        select count(*) as n from public.licencias l
        join public.personas p on p.id = l.persona_id
         where p.numero_documento = %(id)s and l.numero_licencia = %(lic)s
        """,
        {"id": numero, "lic": f"LIC-{numero}"},
    )
    assert n_consultas == 2
    assert n_personas == 1
    assert n_licencias == 1


def test_f05_02_dos_placas_un_vehiculo(repo: ConsultaRepository) -> None:
    """§12.2 / §12.5: 2 consultas misma placa → 1 vehiculos; tipo_documento NULL."""
    placa = _placa_unica("ZZ")
    ids: list[UUID] = []
    for i in range(2):
        r = ResultadoConsulta(
            modo="PLACA",
            identificador=placa,
            tipo_documento=None,
            correlation_id=f"f05-placa-{i}-{placa}",
            iniciado_en=datetime.now(timezone.utc),
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador=placa,
                    modo="PLACA",
                    sin_pendientes=True,
                ),
                raw_html=f"<placa-f05-{i}/>",
            ),
        )
        r.finalizar()
        ids.append(_persistir(repo, r))

    n_consultas = _count(
        repo,
        """
        select count(*) as n from public.consultas
         where modo = 'PLACA' and identificador = %(placa)s
        """,
        {"placa": placa},
    )
    n_vehiculos = _count(
        repo,
        "select count(*) as n from public.vehiculos where placa = %(placa)s",
        {"placa": placa},
    )
    assert n_consultas == 2
    assert n_vehiculos == 1

    with repo._db.connection() as conn:
        for cid in ids:
            row = conn.execute(
                """
                select modo, tipo_documento, vehiculo_id
                  from public.consultas where id = %(id)s
                """,
                {"id": cid},
            ).fetchone()
            assert row is not None
            assert row["modo"] == "PLACA"
            assert row["tipo_documento"] is None
            assert row["vehiculo_id"] is not None


def test_f05_03_documento_obligaciones_simit_con_fks(repo: ConsultaRepository) -> None:
    """§12.3: obligaciones_simit con persona_id y vehiculo_id si hay placa."""
    numero = _numero_documento_unico("806")
    placa = _placa_unica("YY")
    obl_numero = f"OBL-{numero}"
    r = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador=numero,
        tipo_documento="CC",
        correlation_id=f"f05-obl-{numero}",
        iniciado_en=datetime.now(timezone.utc),
        resultado_runt=ResultadoRunt(
            nombre="Con Multa SIMIT",
            tipo_documento="CC",
            numero_documento=numero,
            raw_html="<runt-obl/>",
        ),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador=numero,
                modo="DOCUMENTO",
                comparendos=1,
                sin_pendientes=False,
            ),
            comparendos_multas=[
                ComparendoMulta(
                    numero=obl_numero,
                    tipo="comparendo",
                    placa=placa,
                    estado="PENDIENTE",
                    valor="$ 50.000",
                )
            ],
            raw_html="<simit-obl/>",
        ),
    )
    r.finalizar()
    cid = _persistir(repo, r)

    with repo._db.connection() as conn:
        obl = conn.execute(
            """
            select o.numero, o.persona_id, o.vehiculo_id, v.placa, c.persona_id as c_persona
              from public.obligaciones_simit o
              join public.consultas c on c.id = %(cid)s
              left join public.vehiculos v on v.id = o.vehiculo_id
             where o.numero = %(numero)s
            """,
            {"cid": cid, "numero": obl_numero},
        ).fetchone()
        assert obl is not None
        assert obl["persona_id"] is not None
        assert obl["vehiculo_id"] is not None
        assert obl["placa"] == placa
        assert obl["c_persona"] == obl["persona_id"]

        raw = conn.execute(
            """
            select r.raw_html as raw_runt, s.raw_html as raw_simit
              from public.resultados_runt r
              join public.resultados_simit s on s.consulta_id = r.consulta_id
             where r.consulta_id = %(cid)s
            """,
            {"cid": cid},
        ).fetchone()
    assert raw is not None
    assert raw["raw_runt"] == "<runt-obl/>"
    assert raw["raw_simit"] == "<simit-obl/>"


def test_f05_04_placa_sin_pendientes_sin_obligaciones(repo: ConsultaRepository) -> None:
    """§12.4: PLACA sin_pendientes → vehículo; 0 obligaciones nuevas."""
    placa = _placa_unica("XX")
    r = ResultadoConsulta(
        modo="PLACA",
        identificador=placa,
        tipo_documento=None,
        correlation_id=f"f05-sinpend-{placa}",
        iniciado_en=datetime.now(timezone.utc),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador=placa,
                modo="PLACA",
                sin_pendientes=True,
                comparendos=0,
                multas=0,
            ),
            comparendos_multas=[],
            raw_html="<sin-pend/>",
        ),
    )
    r.finalizar()
    cid = _persistir(repo, r)

    n_veh = _count(
        repo,
        "select count(*) as n from public.vehiculos where placa = %(placa)s",
        {"placa": placa},
    )
    assert n_veh == 1

    with repo._db.connection() as conn:
        row = conn.execute(
            """
            select c.vehiculo_id, s.resumen->>'sin_pendientes' as sin_pend
              from public.consultas c
              join public.resultados_simit s on s.consulta_id = c.id
             where c.id = %(cid)s
            """,
            {"cid": cid},
        ).fetchone()
        assert row is not None
        assert row["vehiculo_id"] is not None
        assert str(row["sin_pend"]).lower() in ("true", "t")

        n_obl = conn.execute(
            """
            select count(*) as n from public.obligaciones_simit
             where vehiculo_id = %(vid)s and last_consulta_id = %(cid)s
            """,
            {"vid": row["vehiculo_id"], "cid": cid},
        ).fetchone()
    assert n_obl is not None
    assert int(n_obl["n"]) == 0


def test_f05_05_sin_elegibilidad_y_raw_html(repo: ConsultaRepository) -> None:
    """§12.6–7: cero columnas elegibilidad; raw_html en resultados_*."""
    _assert_sin_elegibilidad_esquema_v2(repo)
    numero = _numero_documento_unico("807")
    r = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador=numero,
        tipo_documento="CC",
        correlation_id=f"f05-raw-{numero}",
        iniciado_en=datetime.now(timezone.utc),
        resultado_runt=ResultadoRunt(
            nombre="Raw OK",
            tipo_documento="CC",
            numero_documento=numero,
            raw_html="<raw-runt-f05/>",
        ),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador=numero, modo="DOCUMENTO", sin_pendientes=True
            ),
            raw_html="<raw-simit-f05/>",
        ),
    )
    r.finalizar()
    cid = _persistir(repo, r)

    with repo._db.connection() as conn:
        row = conn.execute(
            """
            select r.raw_html as raw_runt, s.raw_html as raw_simit
              from public.resultados_runt r
              join public.resultados_simit s on s.consulta_id = r.consulta_id
             where r.consulta_id = %(cid)s
            """,
            {"cid": cid},
        ).fetchone()
    assert row is not None
    assert row["raw_runt"] == "<raw-runt-f05/>"
    assert row["raw_simit"] == "<raw-simit-f05/>"


def test_f05_06_fallo_normalizacion_conserva_snapshot(repo: ConsultaRepository) -> None:
    """§12.8 / F-02: fallo B/C no invalida capa A ni oculta hechos en memoria."""

    class _RepoNormFail:
        def __init__(self, real: ConsultaRepository) -> None:
            self._real = real

        def persistir_resultado_consulta(self, *args: Any, **kwargs: Any) -> UUID:
            return self._real.persistir_resultado_consulta(*args, **kwargs)

        def agregar_evento(self, *args: Any, **kwargs: Any) -> UUID:
            return self._real.agregar_evento(*args, **kwargs)

        def normalizar_maestros_y_hechos(self, *args: Any, **kwargs: Any) -> dict:
            raise PersistenciaError("F-05 simulación fallo normalización B/C")

    numero = _numero_documento_unico("808")
    r = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador=numero,
        tipo_documento="CC",
        correlation_id=f"f05-normfail-{numero}",
        iniciado_en=datetime.now(timezone.utc),
        resultado_runt=ResultadoRunt(
            nombre="Snapshot Intact",
            raw_html="<snap-runt/>",
        ),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador=numero, modo="DOCUMENTO", sin_pendientes=True
            ),
            raw_html="<snap-simit/>",
        ),
    )
    r.finalizar()

    intentar_persistir_resultado(
        r,
        settings=_settings_ok(),
        repository=_RepoNormFail(repo),  # type: ignore[arg-type]
    )

    assert r.persistido is True
    assert r.consulta_db_id is not None
    assert r.error_persistencia is None
    assert r.resultado_runt is not None
    assert r.resultado_runt.nombre == "Snapshot Intact"

    leido = repo.obtener_por_id(r.consulta_db_id)
    assert leido is not None
    assert leido.resultado_runt is not None
    assert leido.resultado_runt.raw_html == "<snap-runt/>"
    assert leido.resultado_simit is not None
    assert leido.resultado_simit.raw_html == "<snap-simit/>"
