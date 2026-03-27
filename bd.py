import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def conexionbd():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dbname=os.getenv("DB_NAME"),
        #port=os.getenv("DB_PORT", 5432)
        port=5432
    )


def execute_query(query, params=None, fetch=False):
    conexion = None
    cursor = None
    try:
        conexion = conexionbd()
        cursor = conexion.cursor()

        cursor.execute(query, params or ())

        if fetch:
            columns = [desc[0] for desc in cursor.description]
            result = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        else:
            conexion.commit()
            try:
                result = cursor.fetchone()[0]
            except:
                result = None

        return result

    except Exception as e:
        if conexion:
            conexion.rollback()
        raise e

    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()