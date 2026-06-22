from headroom.compress import compress

messy_log = """
[2023-10-27T10:00:00.000Z] INFO [main] com.example.MyClass - Starting up...
[2023-10-27T10:00:00.100Z] DEBUG [main] com.example.MyClass - Loading config
[2023-10-27T10:00:00.200Z] DEBUG [main] com.example.MyClass - Config loaded successfully
[2023-10-27T10:00:00.300Z] INFO [main] com.example.MyClass - Connecting to database
[2023-10-27T10:00:00.400Z] DEBUG [main] com.example.MyClass - Connection pool created
[2023-10-27T10:00:00.500Z] WARN [main] com.example.MyClass - Retrying connection (1/3)
[2023-10-27T10:00:00.600Z] WARN [main] com.example.MyClass - Retrying connection (2/3)
[2023-10-27T10:00:00.700Z] WARN [main] com.example.MyClass - Retrying connection (3/3)
[2023-10-27T10:00:00.800Z] ERROR [main] com.example.MyClass - FATAL: Database connection failed!
java.sql.SQLException: Connection refused
    at com.example.db.ConnectionFactory.create(ConnectionFactory.java:45)
    at com.example.db.ConnectionPool.init(ConnectionPool.java:120)
    at com.example.MyClass.start(MyClass.java:88)
    at com.example.Main.main(Main.java:15)
[2023-10-27T10:00:00.900Z] INFO [main] com.example.MyClass - Shutting down...
""" * 50

messages = [{"role": "user", "content": f"```log\n{messy_log}\n```"}]
result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
print(result.transforms_applied)
