# This HLA takes a stream of bytes (preferably ascii characters) and combines individual frames into larger frames in an attempt to make text strings easier to read.
# For example, this should make reading serial log messages much easier in the software.
# It supports delimiting on special characters, and after a certain delay is detected between characters.
# It supports the I2C, SPI, and Serial analyzers, although it's most useful for serial port messages.


# Settings constants.
MESSAGE_PREFIX_SETTING = 'Message Prefix (optional)'
PACKET_TIMEOUT_SETTING = 'Packet Timeout [s]'
PACKET_DELIMITER_SETTING = 'Packet Delimiter'

DELIMITER_CHOICES = {
    'New Line [\\n]': '\n',
    'Null [\\0]': '\0',
    'Space [\' \']': ' ',
    'Semicolon [;]': ';',
    'Tab [\\t]': '\t'
}


class TextMessages():

    temp_frame = None

    # user selected settings used while decoding
    prefix = ''
    delimiter = '\n'
    packet_timeout = 0.5E-3

    def __init__(self):
        pass

    def get_capabilities(self):
        # called once when the HLA is loaded.
        # no return value is required, but one can be provided to show settings in the Logic software UI.
        # to provide settings, return a dictionary with a "settings" key, that holds a dictionary of individual settings.
        # there are three types of settings, "string", "number", and "choices"
        # the each key inside of the settings dictionary will be the title of each setting UI.
        # each setting item requires a "type" field, "string", "number", or "choices"
        # "string" settings have no other fields.
        # "number" settings optionally support "minimum" and "maximum", but they are not required.
        # "choices" settings require an array of string called "choices", which are the items to display in the drop-down box in the UI.
        # Once the user selects their settings, their selections will be passed to the "set_settings" class method below.
        return {
            'settings': {
                MESSAGE_PREFIX_SETTING: {
                    'type': 'string'
                },
                PACKET_TIMEOUT_SETTING: {
                    'type': 'number',
                    'minimum': 1E-6,
                    'maximum': 1E4
                },
                PACKET_DELIMITER_SETTING: {
                    'type': 'choices',
                    'choices': DELIMITER_CHOICES.keys()
                }
            }
        }

    def set_settings(self, settings):
        print("hello from python!")
        # this function returns the formatting strings required for the UI to display the HLA output frames.
        # If settings were made available from the "get_capabilities" class method above, the user selections will be passed in here.
        # This function also serves as a reset signal, in case the HLA is going to be re-run over the same capture.

        # Settings
        # for every key in the "settings" dictionary returned by get_capabilities, there will be a matching key in the "settings" parameter here.
        # the value for each key is either a string or a number, based on the "type" specified in the settings in get_capabilities
        if MESSAGE_PREFIX_SETTING in settings.keys():
            self.prefix = settings[MESSAGE_PREFIX_SETTING]
        if PACKET_TIMEOUT_SETTING in settings.keys():
            self.packet_timeout = settings[PACKET_TIMEOUT_SETTING]
        if PACKET_DELIMITER_SETTING in settings.keys():
            delimiter_selection = settings[PACKET_DELIMITER_SETTING]
            if delimiter_selection in DELIMITER_CHOICES.keys():
                self.delimiter = DELIMITER_CHOICES[delimiter_selection]

        # here, we need to return a format string for every distinct value of "type" in the frames returned by the "decode" class method.
        # for example, in this HLA, we have two types of frames, "error" and "message". "error" isn't actually used at the moment though.
        # we need to return a dictionary with a key named "result_types", which is a dictionary with one key per distinct frame type.
        # for each frame type key, we need to provide a "format" value, which uses the mustache template syntax.
        # details here: https://mustache.github.io/mustache.5.html
        # the template string has access to the complete frame returned by the HLA.
        # most interesting information will be placed in the "data" member of the frame, which is a dictionary.

        return {
            'result_types': {
                'error': {
                    'format': 'Error!'
                },
                "message": {
                    'format': self.prefix + '{{data.str}}'
                }
            }
        }

    def clear_stored_message(self, data):
        self.temp_frame = {
            "type": "message",
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "data": {
                "str": "",
            }
        }

    def append_char(self, char):
        self.temp_frame["data"]["str"] += char

    def have_existing_message(self):
        if self.temp_frame is None:
            return False
        if len(self.temp_frame["data"]["str"]) == 0:
            return False
        return True

    def update_end_time(self, data):
        self.temp_frame["end_time"] = data["end_time"]

    def decode(self, data):
        # This class method is called once for each frame produced by the input analyzer.
        # the "data" dictionary contents is specific to the input analyzer type. The readme with this repo contains a description of the "data" contents for each input analyzer type.
        # all frames contain some common keys: start_time, end_time, and type.

        # This function can either return nothing, a single new frame, or an array of new frames.
        # all new frames produced are dictionaries and need to have the required keys: start_time, end_time, and type
        # in addition, protocol-specific information should be stored in the "data" key, so that they can be accessed by rendering (using the format strings), by export, by the terminal view, and by the protocol search results list.
        # Not all of these are implemented yet, but we're working on it!

        # All protocols - use the delimiter specified in the settings.
        delimiters = [self.delimiter]  # [ "\0", "\n", "\r", " " ]
        # All protocols - delimit on a delay specified in the settings
        # 0.5E-3 # consider frames further apart than this separate messages
        maximum_delay = self.packet_timeout
        # I2C - delimit on address byte
        # SPI - delimit on Enable toggle. TODO: add support for the SPI analyzer to send Enable/disable frames, or at least a Packet ID to the low level analyzer.

        frame_start = data["start_time"]
        frame_end = data["end_time"]

        char = "unknown error."

        # setup initial result, if not present
        first_frame = False
        if self.temp_frame is None:
            first_frame = True
            self.clear_stored_message(data)

        # handle serial data
        if data["type"] == "data" and "value" in data["data"].keys():
            value = data["data"]["value"]
            char = chr(value)

        # handle I2C address
        if data["type"] == "address":
            value = data["data"]["address"][0]
            # if we have an existing message, send it
            if self.have_existing_message() == True:
                ret = self.temp_frame
                self.clear_stored_message(data)
                self.append_char("address: " + hex(value) + ";")
                print('new frame contents: ' + ret["data"]["str"].rstrip())
                return ret
            # append the address to the beginning of the new message
            self.append_char("address: " + hex(value) + ";")
            return None

        # handle I2C data byte
        if data["type"] == "data" and "data" in data["data"].keys() and type(data["data"]["data"]) is bytes:
            value = data["data"]["data"][0]
            char = chr(value)

        # handle I2C start condition
        if data["type"] == "start":
            return

        # handle I2C stop condition
        if data["type"] == "stop":
            if self.have_existing_message() == True:
                ret = self.temp_frame
                self.temp_frame = None
                print('new frame contents: ' + ret["data"]["str"].rstrip())
                return ret
            self.temp_frame = None
            return

        # handle SPI byte
        if data["type"] == "result":
            char = ""
            if "miso" in data["data"].keys() and data["data"]["miso"] != 0:
                char += chr(data["data"]["miso"])
            if "mosi" in data["data"].keys() and data["data"]["mosi"] != 0:
                char += chr(data["data"]["mosi"])

        # If we have a timeout event, commit the frame and make sure not to add the new frame after the delay, and add the current character to the next frame.
        if first_frame == False and self.temp_frame is not None:
            if self.temp_frame["end_time"] + maximum_delay < frame_start:
                ret = self.temp_frame
                self.clear_stored_message(data)
                self.append_char(char)
                print('new frame contents: ' + ret["data"]["str"].rstrip())
                return ret

        self.append_char(char)
        self.update_end_time(data)

        # if the current character is a delimiter, commit it.
        if char in delimiters:
            ret = self.temp_frame
            # leave the temp_frame blank, so the next frame is the beginning of the next message.
            self.temp_frame = None
            print('new frame contents: ' + ret["data"]["str"].rstrip())
            return ret
