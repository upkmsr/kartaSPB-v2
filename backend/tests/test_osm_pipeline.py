from sqlalchemy import make_url

from app.data.osm.pipeline import _osm2pgsql_connection


def test_osm2pgsql_connection_keeps_password_out_of_arguments() -> None:
    arguments, environment = _osm2pgsql_connection(
        make_url("postgresql+psycopg://osm-user:sensitive@db:5544/osm-db")
    )

    assert arguments == [
        "--host=db",
        "--port=5544",
        "--database=osm-db",
        "--username=osm-user",
    ]
    assert "sensitive" not in " ".join(arguments)
    assert environment["PGPASSWORD"] == "sensitive"
