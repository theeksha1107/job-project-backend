# import mysql.connector
# from mysql.connector import Error
 
# def get_db_connection():
#     try:
#         connection = mysql.connector.connect(
#             host="localhost",
#             user="root",
#             password="thee@1124",  # Replace with your MySQL root password
#             database="employee1_db"
#         )
#         return connection
#     except Error as e:
#         print("Error connecting to MySQL", e)
#         return None
import mysql.connector
from mysql.connector import Error
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('db_connection.log'),  # Log to a file
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger(__name__)

def get_db_connection():
    logger.info("Attempting to connect to MySQL database")
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="thee@1124",  # Replace with your MySQL root password
            database="employee1_db"
        )
        logger.info("Connection object created")
        if connection.is_connected():
            logger.info("Successfully connected to MySQL database: %s", connection.get_server_info())
        else:
            logger.warning("Connection object exists but is not connected")
        return connection
    except Error as e:
        logger.error("Error connecting to MySQL: %s", e)
        return None
    finally:
        logger.info("get_db_connection function execution completed")