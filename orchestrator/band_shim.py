import asyncio
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

class BandRoom:
    """
    Simulates the Band SDK room environment for decentralized agent communication.
    Agents can subscribe to event topics and publish structured context.
    """
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.subscribers: Dict[str, List[Callable]] = {}
        self.context_store: Dict[str, Any] = {}

    def subscribe(self, topic: str, callback: Callable):
        """Subscribe an agent callback to a topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
        logger.debug(f"[BandRoom-{self.room_id}] Subscribed to topic: {topic}")

    async def publish(self, topic: str, data: Any):
        """Publish structured context to the room."""
        logger.info(f"[BandRoom-{self.room_id}] Event Published: {topic}")
        # Store context globally for late joiners or shared state
        self.context_store[topic] = data
        
        if topic in self.subscribers:
            # Trigger all subscribed agents asynchronously
            tasks = [callback(data) for callback in self.subscribers[topic]]
            if tasks:
                await asyncio.gather(*tasks)

    def get_context(self, topic: str) -> Any:
        """Retrieve stored context from the room."""
        return self.context_store.get(topic)
