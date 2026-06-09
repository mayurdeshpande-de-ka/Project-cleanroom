import os
import psycopg2
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def explore_tables():
    # Read environment variables
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    # Debug prints (remove later if needed)
    print("---- DB CONFIG ----")
    print("HOST :", db_host)
    print("PORT :", db_port)
    print("USER :", db_user)
    print("DB   :", db_name)
    print("-------------------")

    # Validate env variables
    missing = []

    if not db_host:
        missing.append("DB_HOST")
    if not db_user:
        missing.append("DB_USER")
    if not db_pass:
        missing.append("DB_PASSWORD")
    if not db_name:
        missing.append("DB_NAME")

    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        return

    try:
        print("\nConnecting to PostgreSQL...\n")

        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_pass,
            dbname=db_name
        )

        print("Connection successful!\n")

        with conn.cursor() as cur:

            # =========================
            # election table
            # =========================
            print("----- TABLE: election -----")

            try:
                cur.execute("SELECT * FROM public.election LIMIT 5;")

                colnames = [desc[0] for desc in cur.description]
                print("Columns:", colnames)

                rows = cur.fetchall()

                for row in rows:
                    print(row)

            except Exception as e:
                print("Error querying election table:")
                print(e)
                conn.rollback()

            # =========================
            # ac_election_mapping table
            # =========================
            print("\n----- TABLE: ac_election_mapping -----")

            try:
                cur.execute(
                    "SELECT * FROM public.ac_election_mapping LIMIT 5;"
                )

                colnames = [desc[0] for desc in cur.description]
                print("Columns:", colnames)

                rows = cur.fetchall()

                for row in rows:
                    print(row)

            except Exception as e:
                print("Error querying ac_election_mapping table:")
                print(e)
                conn.rollback()

        conn.close()
        print("\nConnection closed.")

    except Exception as e:
        print("\nConnection failed:")
        print(e)


if __name__ == "__main__":
    explore_tables()