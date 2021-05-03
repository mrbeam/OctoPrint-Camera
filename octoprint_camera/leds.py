import datetime
import logging
from octoprint.events import Events, GenericEventListener
from octoprint_mrbeam import led_events

class LedEventListener(led_events.LedEventListener):
    def __init__(self, plugin):
        # Do not disturb the lights with client connections
        self.LED_EVENTS[Events.STARTUP] = "echo not doing anything"
        self.LED_EVENTS[Events.CLIENT_OPENED] = "echo not doing anything"
        self.LED_EVENTS[Events.CLIENT_CLOSED] = "echo not doing anything"
        # Do not use the CommandTrigger class because we do not have a printer
        self._plugin = plugin
        self._event_bus = plugin._event_bus
        self._logger = logging.getLogger(__name__)
        self._watch_thread = None
        self._watch_active = False
        self._listening_state = None
        self._analytics_handler = None
        self._subscriptions = {}

        self._connections_states = []
        # Addition : immediatly subscribe to events
        self._initSubscriptions()
        self._logger.warning("INIT LEDS subcriptions : %s", self._subscriptions)
    
    def eventCallback(self, event, payload=None):
        self._logger.warning("EVENT %s", event)
        GenericEventListener.eventCallback(self, event, payload)

        if not event in self._subscriptions:
            return

        for command, commandType, debug in self._subscriptions[event]:
            self._execute_command(command, commandType, debug, event, payload)

    def log_listening_state(self, command=None):
        pass

    def _get_listening_command(self):
        command = self.LED_EVENTS[Events.STARTUP]
        if self._listening_state is not None and (
            self._listening_state["findmrbeam"] is not None
        ):
            if self._listening_state["findmrbeam"]:
                command = self.COMMAND_LISTENING_FINDMRBEAM
            elif self._listening_state["ap"] and (
                self._listening_state["wifi"] or self._listening_state["wired"]
            ):
                command = self.COMMAND_LISTENING_AP_AND_NET
            elif self._listening_state["ap"] and not (
                self._listening_state["wifi"] or self._listening_state["wired"]
            ):
                command = self.COMMAND_LISTENING_AP
            elif self._listening_state["wifi"] or self._listening_state["wired"]:
                command = self.COMMAND_LISTENING_NET
        self.log_listening_state(command=command)
        return command
    
    def _processCommand(self, command, payload):
        # Remove self._printer logic
        json_string = "{}"
        if payload:
            import json
            try:
                json_string = json.dumps(payload)
            except:
                json_string = ""
        params = {
            "__currentZ": "-1",
            "__filename": "NO FILE",
            "__filepath": "NO PATH",
            "__progress": "0",
            "__data": str(payload),
            "__json": json_string,
            "__now": datetime.datetime.now().isoformat()
        }
        # now add the payload keys as well
        if isinstance(payload, dict):
            params.update(payload)

        return command.format(**params)
    
    def _executeGcodeCommand(self, command, debug=False):
        pass