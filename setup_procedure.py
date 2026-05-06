import pyodbc
from config import get_db_connection_params

# Get connection parameters
db_params = get_db_connection_params()
driver = db_params['driver']
server = db_params['server']
database = db_params['database']
username = db_params.get('username')
password = db_params.get('password')

conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
if username and password:
    conn_str += f"UID={username};PWD={password};"
else:
    conn_str += "Trusted_Connection=yes;"

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Execute the procedure creation
sql = """
IF OBJECT_ID('dbo.usp_GetDoctorByUserId', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_GetDoctorByUserId;
GO
CREATE PROCEDURE dbo.usp_GetDoctorByUserId
    @user_id INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT d.*, CONCAT('Dr. ', d.first_name, ' ', d.last_name) AS full_name
    FROM Doctors d
    WHERE d.user_id = @user_id;
END
"""

try:
    # Split by GO and execute each statement
    for statement in sql.split('GO'):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)
    conn.commit()
    print("[OK] Procedure usp_GetDoctorByUserId created successfully")
except Exception as e:
    print(f"[ERROR] Failed to create procedure: {e}")
finally:
    cursor.close()
    conn.close()
