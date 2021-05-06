# coding=utf-8
from __future__ import absolute_import, print_function, unicode_literals, division
from octoprint_mrbeam.iobeam import iobeam_handler
from octoprint_mrbeam.iobeam.iobeam_handler import IoBeamEvents

# TODO - pahse 3: Create a separate iobeam plugin

IoBeamEvents


class IoBeamHandler(iobeam_handler.IoBeamHandler):
    def _handle_dataset(self, name, dataset):
        # We only care about the one_btn, which is part of the pcf dataset
        if name == self.DATASET_PCF:
            return self._handle_pcf(dataset)
        else:
            return 0

    def _handle_pcf(self, dataset):
        if self.MESSAGE_DEVICE_ONEBUTTON in dataset:
            self._handle_onebutton(dataset[self.MESSAGE_DEVICE_ONEBUTTON])
        return 0

    def get_client_msg(self):
        """
        Make and return client identification message in required format
        :return: client identification message
        """
        # Had to override the function to fix version tag
        return {
            "client": {
                "name": self.CLIENT_NAME,
                "version": "some_version",
                "config": {"send_initial_data": True, "update_interval": True},
            }
        }
