from datetime import datetime, timedelta


class MemoryManager:

    def __init__(self, ttl_minutes=30):

        self.ttl = timedelta(minutes=ttl_minutes)

        self.last_updated = {}

    def touch(self, user_id: str):

        self.last_updated[user_id] = datetime.utcnow()

    def should_expire(self, user_id: str):

        if user_id not in self.last_updated:
            return False

        return datetime.utcnow() - self.last_updated[user_id] > self.ttl

    def cleanup(self, user_id: str, conversation_memory):

        if self.should_expire(user_id):

            conversation_memory.clear_user(user_id)

            del self.last_updated[user_id]

            return True

        return False

    def clear(self, user_id: str):

        self.last_updated.pop(user_id, None)


if __name__ == "__main__":

    manager = MemoryManager(ttl_minutes=30)

    manager.touch("user_1")

    print("User memory expired:")
    print(manager.should_expire("user_1"))

    manager.clear("user_1")

    print("Memory manager test completed.")