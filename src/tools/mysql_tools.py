import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "employee"),
        )
    except mysql.connector.Error as err:
        raise ConnectionError(f"Failed to connect to database: {err}")


def get_employees_by_id(emp_id: str) -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM employee_data WHERE employee_id = %s", (emp_id,)
            )
            result = cursor.fetchone()
            return [result] if result else []
    finally:
        conn.close()


def get_employees_by_department(department: str) -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM employee_data WHERE department = %s", (department,)
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_employees_by_name(name: str) -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM employee_data WHERE name LIKE %s", (f"%{name}%",)
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_all_employees() -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM employee_data")
            return cursor.fetchall()
    finally:
        conn.close()


def get_all_departments() -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT DISTINCT department FROM employee_data")
            return [row["department"] for row in cursor.fetchall() if row["department"]]
    finally:
        conn.close()


def get_employees_by_role(role: str) -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM employee_data WHERE role LIKE %s", (f"%{role}%",)
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_employees_by_email(email_pattern: str) -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM employee_data WHERE email LIKE %s",
                (f"%{email_pattern}%",),
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_all_roles() -> list:
    conn = get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT DISTINCT role FROM employee_data")
            return [row["role"] for row in cursor.fetchall() if row["role"]]
    finally:
        conn.close()


def insert_employee(
    emp_id: str, name: str, email: str, department: str, role: str
) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            query = """
            INSERT INTO employee_data (employee_id, name, email, department, role)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (emp_id, name, email, department, role))
        conn.commit()
        return True
    except mysql.connector.Error as err:
        conn.rollback()
        raise RuntimeError(f"Failed to insert employee: {err}")
    finally:
        conn.close()


def update_employee(
    emp_id: str,
    name: str | None = None,
    email: str | None = None,
    department: str | None = None,
    role: str | None = None,
) -> bool:
    conn = get_connection()
    try:
        fields = []
        values = []
        if name:
            fields.append("name = %s")
            values.append(name)
        if email:
            fields.append("email = %s")
            values.append(email)
        if department:
            fields.append("department = %s")
            values.append(department)
        if role:
            fields.append("role = %s")
            values.append(role)

        if not fields:
            raise ValueError("No fields to update")

        values.append(emp_id)
        query = f"UPDATE employee_data SET {', '.join(fields)} WHERE employee_id = %s"

        with conn.cursor() as cursor:
            cursor.execute(query, tuple(values))
        conn.commit()
        return cursor.rowcount > 0
    except mysql.connector.Error as err:
        conn.rollback()
        raise RuntimeError(f"Failed to update employee: {err}")
    finally:
        conn.close()


def delete_employee(emp_id: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM employee_data WHERE employee_id = %s", (emp_id,)
            )
        conn.commit()
        return cursor.rowcount > 0
    except mysql.connector.Error as err:
        conn.rollback()
        raise RuntimeError(f"Failed to delete employee: {err}")
    finally:
        conn.close()
