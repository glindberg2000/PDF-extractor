import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection parameters
db_params = {
    "dbname": "mydatabase",
    "user": "newuser",
    "password": "newpassword",
    "host": "localhost",
    "port": "5432",
}


def check_migrations():
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get all migrations
        cur.execute(
            """
            SELECT id, name, applied 
            FROM django_migrations 
            WHERE app = 'profiles' 
            ORDER BY id;
        """
        )

        print("\nApplied migrations:")
        for row in cur.fetchall():
            print(f"{row['id']}: {row['name']} (applied: {row['applied']})")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_migrations()
