from utils.aci import *

class HistoryProcessor():
	"""
	Agent history message processor.
	"""
	def __init__(self, logger: logging.Logger):
		self.logger = logger
		self.history = []
		self.last = []
		self.temp = ""

	def extend_msg(self, msg: list, response_text: str, content: str):
		"""
		Extends the history message to get a new messeage for query.
		"""
		new_msg = [
				{ "role": "assistant", "content": response_text },
				{ "role": "user", "content": content},
		]
		msg.extend(new_msg)
		self.logger.info(f"Query\n{content}")

	def record_history(self, msg: list):
		"""
		Record the message history.
		"""
		self.history = msg

	def record_last_msg(self, response_text: str, content: str):
		"""
		Record the last message.
		"""
		msg = [
				{ "role": "assistant", "content": response_text },
				{ "role": "user", "content": content},
		]
		self.last = msg
