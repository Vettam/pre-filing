import logging
import traceback
import sys


class UnifiedErrorFormatter(logging.Formatter):
    """
    Custom formatter that includes tracebacks in the same log entry
    instead of printing them as separate lines.
    """
    
    def format(self, record):
        # Format the base message
        formatted = f"{record.levelname} {self.formatTime(record)} {record.module}\n{record.getMessage()}"
        
        # If there's exception info, add it to the same log entry
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            
            if record.exc_text:
                # Add traceback to the same log entry, indented for readability
                traceback_lines = record.exc_text.strip().split('\n')
                indented_traceback = '\n'.join(f"  {line}" for line in traceback_lines)
                formatted += f"\n{indented_traceback}"
        
        return formatted


class LoggingHandler:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LoggingHandler, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        self.logger = logging.getLogger("bare_acts")
        self.logger.setLevel(logging.INFO)
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(UnifiedErrorFormatter())
        self.logger.addHandler(stream_handler)

    def info(self, message):
        self.logger.info(message)

    def warn(self, message):
        self.logger.warning(message)

    def error(self, message, exc_info=None):
        if exc_info:
            # Include full traceback
            tb_str = "".join(
                traceback.format_exception(
                    type(exc_info), exc_info, exc_info.__traceback__
                )
            )
            full_message = f"{message}\nFull Traceback:\n{tb_str}"
            self.logger.error(full_message)
        else:
            self.logger.error(message)
    
    def exception(self, message):
        """Log an exception with full traceback"""
        self.logger.exception(message)
    
    def log_exception(self, message, exception=None, request=None):
        """
        Enhanced exception logging with full context - only for errors
        """
        import sys
        
        # Get current exception info if not provided
        if exception is None:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            exception = exc_value
        else:
            exc_type = type(exception)
            exc_value = exception
            exc_traceback = exception.__traceback__
        
        if exc_traceback is not None:
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            full_traceback = ''.join(tb_lines)
            
            # Build comprehensive error message
            error_details = [
                f"Error: {message}",
                f"Exception: {exc_type.__name__}: {str(exception)}"
            ]
            
            if request:
                error_details.extend([
                    f"Request: {request.method} {request.path}",
                    f"User: {getattr(request, 'user', 'Anonymous')}"
                ])
                
                # Add request body if available (truncate if too long)
                body = getattr(request, 'body', b'')
                if body:
                    body_str = body.decode('utf-8', errors='ignore')[:500]
                    error_details.append(f"Request Body: {body_str}")
            
            error_details.append(f"\nFull Traceback:\n{full_traceback}")
            
            full_message = '\n'.join(error_details)
            self.logger.error(full_message)
        else:
            self.logger.error(f"{message}: {str(exception)}")


# Initialize logger
logger = LoggingHandler()
