import mysql.connector
from mysql.connector import Error
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('db_connection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_db_connection():
    logger.info("Attempting to connect to Azure MySQL database (without SSL)")
    try:
        connection = mysql.connector.connect(
            host="customerdatabase.mysql.database.azure.com",
            port=3306,
            user="mysqladmin",  # Must include @server-name
            password="mypassword@123",                # Replace with your actual password
            database="employee1_db"              # Replace with your actual database name
        )
        logger.info("Connection object created")
        if connection.is_connected():
            logger.info("Successfully connected to Azure MySQL database: %s", connection.get_server_info())
        else:
            logger.warning("Connection object exists but is not connected")
        return connection
    except Error as e:
        logger.error("Error connecting to Azure MySQL: %s", e)
        return None
    finally:
        logger.info("get_db_connection function execution completed")
