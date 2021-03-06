# -*- coding: utf-8 -*-
"""
Created on Fri Jun 21 17:19:35 2013

@author: pfduc
"""
import sys, io
from collections import OrderedDict
from importlib import import_module

from numpy import nan

from PyQt4.QtGui import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPlainTextEdit,QPushButton,QComboBox,QPalette,QColor
from PyQt4.QtCore import SIGNAL,QObject

import numpy as np

try:
    
    import LabDrivers.utils as utils
    
except:
    
    import utils

try:
    
    import visa
    visa_available = True
    
except:
    
    visa_available = False
    print("you will need visa to use most drivers")

try:
    
    import serial
    serial_available = True
    
except:
    
    serial_available = False
    print("pyserial not available")


# Use these constants to identify interface type.
# Avoids case-sensitivity/typo issues if you were to use the strings directly
# these are imported by the instrument drivers so keep them there even if your
# editor tells you that utils.INTF_NONE isn't used
from utils import INTF_VISA, INTF_SERIAL, INTF_PROLOGIX, INTF_NONE, INTF_GPIB \
                    ,PROLOGIX_COM_PORT, refresh_device_port_list

import logging
logging.basicConfig(level=logging.DEBUG)

old_visa = True
try:
    # poke at something that only exists in older versions of visa, as a probe
    # for the version
    visa.term_chars_end_input
    logging.info("using pyvisa version less than 1.6")
    
except:
    
    old_visa = False
    logging.info("using pyvisa version higher than 1.6")

 # Tobe moved into InstrumentHub class as this class should only be GUI





class MeasInstr(object):
    """
    Class of a measure instrument this is designed to be a parent class
    from which any new instrument driver should inherit, this way one
    avoid redefining features common to most instruments
    It entails connecting to the instrument (connect), talking to it
    (ask, read, write) and measuring (measure, only defined here as an
    empty method, any child class should redefine it)
    """

    # identify the instrument in a unique way
    ID_name = None
    # store the pyvisa object connecting to the hardware
    connection = None
    # debug mode trigger
    debug = False
    # contains the different channels availiable
    channels = []
    # store the instrument last measure in the different channels
    last_measure = {}
    # contains the units of the different channels
    units = {}
    # contains the name of the different channels if the channels do not have
    # explicit names
    channels_names = {}

    # the name of the communication port
    resource_name = ''

    #**kwargs can be any of the following param "timeout", "term_chars","chunk_size", "lock","delay", "send_end","values_format"
    # example inst=MeasInstr('GPIB0::0','Inst_name',True,timeout=12,term_char='\n')
    # other exemple inst=MeasInstr('GPIB0::0',timeout=12,term_char='\n')
    def __init__(self, resource_name, name = 'default', debug = False,
                 interface = None, **kwargs):
        """
            use interface = None if the instrument will not inherit read and 
            write functionality from Tool for example TIME, DICE, ZH_HF2 and 
            other highly custom instruments
        """

        self.ID_name = name
        # one of these two should disappear, but we need to look into the bugs
        # it might create first
        self.DEBUG = debug
        #self.resource_name = resource_name
        

        self.term_chars=""        

        self.interface = interface

        if self.interface == INTF_VISA:
            
            if not old_visa:
                
                self.resource_manager = visa.ResourceManager()

        if self.interface == INTF_PROLOGIX:
            # there is only one COM port that the prologix has, then we go
            # through that for all GPIB communications

            if INTF_PROLOGIX in kwargs:
                # the connection is passed as an argument

                if isinstance(kwargs[INTF_PROLOGIX], str):
                    # it was the COM PORT number so we initiate an instance
                    # of prologix controller
                    if "COM" in kwargs[INTF_PROLOGIX]:
                        self.connection = utils.PrologixController(
                            kwargs[INTF_PROLOGIX])

                else:
                    # it was the PrologixController instance
                    self.connection = kwargs[INTF_PROLOGIX]
                    
                    if "Prologix GPIB-USB Controller" in self.connection.controller_id():
                        pass
                    
                    else:
                        
                        logging.error(
                            "The controller passed as an argument is not the good one")

            else:
                # the connection doesn't exist so we create it
                self.connection = utils.PrologixController()

        # load the parameters and their unit for an instrument from the values
        # contained in the global variable of the latter's module
        if name != 'default':

            try:
                
                module_name = import_module(
                    "." + name, package=utils.LABDRIVER_PACKAGE_NAME)
                    
            except ImportError:
                module_name = import_module(
                    name, package=utils.LABDRIVER_PACKAGE_NAME)
#            else:
#                module_name=import_module("."+name,package=LABDRIVER_PACKAGE_NAME)
            self.channels = []
            
            for chan, u in list(module_name.param.items()):
                # initializes the first measured value to 0 and the channels'
                # names
                self.channels.append(chan)
                self.units[chan] = u
                self.last_measure[chan] = 0
                self.channels_names[chan] = chan

        # establishs a connection with the instrument
        # this check should be based on interface, not resource_name
        # the check is now performed in self.connect, deprecating this if statement
        # if not resource_name == None:
        self.connect(resource_name, **kwargs)

    def initialize(self):
        """
        Instruments may overload this function to do something when the
        script first starts running (as opposed to immediately when connected)
        For example, noting the time the run started
        """
        pass

    def __str__(self):
        
        return self.identify()

    def identify(self, msg=''):
        """ Try the IEEE standard identification request """
        
        if not self.DEBUG:
            
            id_string = str(self.ask('*IDN?'))
            
            if not id_string == None:
                
                return msg + id_string
                
            else:
                
                return "Unknown instrument"
                
        else:
            
            return msg + self.ID_name

    def read(self, num_bytes=None):
        """ Reads data available on the port (up to a newline char) """
        if not self.DEBUG:
            
            if self.interface == INTF_VISA:
                
                answer = self.connection.read()

            elif self.interface == INTF_SERIAL or self.interface == INTF_PROLOGIX:
                
                if not num_bytes == None:
                    
                    answer = self.connection.read(num_bytes)
                    
                else:
                    
                    answer = self.connection.readline()

                # remove the newline character if it is at the end
                if len(answer) > 1:
                    
                    if answer[-1:] == '\n':
                        
                        answer = answer[:-1]
                        
                if len(answer) > 1:
                    
                    if answer[-1] == '\r':
                        
                        answer = answer[:-1]

        else:
            
            answer = None
            
        return answer

    def write(self, msg):
        """ 
            Writes command to the instrument but does not check for a response
        """
        
        if not self.DEBUG:
            
            if self.interface == INTF_PROLOGIX:
                # make sure the address is the right one (might be faster to
                # check for that, might be not)
                self.connection.write("++addr %s" % (self.resource_name))
            answer = self.connection.write(msg + self.term_chars)
            
        else:
            
            answer = msg
            
        return answer

    def ask(self, msg, num_bytes=None):
        """ Writes a command to the instrument and reads its reply """
        
        answer = None
        
        if not self.DEBUG:
            
            if self.interface == INTF_VISA:
                
                try:
                    
                    answer = self.connection.ask(msg)
                    
                except:
                    print("\n\n### command %s bugged###\n\n"%msg)
                    answer = np.nan
                
            elif self.interface == INTF_SERIAL or self.interface == INTF_PROLOGIX:
                
                try:
                    
                    self.write(msg)
                    answer = self.read(num_bytes)
                    
                except:
                    print("\n\n### command %s bugged###\n\n"%msg)
                    answer = np.nan
        else:
            answer = msg
        return answer

    def connect(self, resource_name, **keyw):
        """Trigger the physical connection to the instrument"""
        
        logging.info("\nMy interface is %s\n" % (self.interface))
        for a in keyw:
            logging.debug(a)

        if not self.DEBUG:

            if self.interface == INTF_VISA:
                
                self.close()
                
                if old_visa:
                    
                    self.connection = visa.instrument(resource_name, **keyw)
                    self.resource_name = resource_name
                    
                else:
                    
                    logging.debug("using pyvisa version higher than 1.6")
                    self.connection = self.resource_manager.get_instrument(
                        resource_name, **keyw)
                        
                self.resource_name = resource_name

            elif self.interface == INTF_SERIAL:
                
                self.close()
                logging.debug(keyw)
                
                if "term_chars" in keyw:
                    
                    self.term_chars = keyw["term_chars"]
                    keyw.pop("term_chars")
                    
                if "baud_rate" in keyw:
                    
                    baud_rate = keyw["baud_rate"]
                    keyw.pop("baud_rate")
                    self.connection = serial.Serial(
                        resource_name, baud_rate, **keyw)
                        
                else:
                    
                    self.connection = serial.Serial(resource_name)
                    
                self.resource_name = resource_name

            elif self.interface == INTF_PROLOGIX:
                # only keeps the number of the port
                self.resource_name = resource_name.replace('GPIB0::', '')

                self.connection.write(("++addr %s" % (self.resource_name)))
                self.connection.readline()
                # the \n termchar is embedded in the PrologixController class
                self.term_chars = ""

            else:
                # instruments like TIME and DICE don't have a resource name
                # so just set it to their ID name
                if resource_name == None:
                    
                    self.resource_name = self.ID_name
                    
                else:
                    
                    self.resource_name = resource_name
                    
                print("setting default resource name to ", self.resource_name)
                # all others must take care of their own communication


            logging.info("connected to " + str(resource_name))


    def close(self):
        """Close the connection to the instrument"""
        if not self.connection == None:
            
            try:
                
                self.connection.close()
                logging.debug("disconnect " + self.ID_name)
                
            except:
                
                logging.debug("unable to disconnect  " + self.ID_name)

    def clear(self):
        """Clear the conneciton to the instrument"""
        if not self.connection == None:
            
            try:
                
                if self.interface == INTF_VISA:
                    
                    self.connection.clear()
                    print(("cleared " + self.ID_name))
                    
            except:
                
                print(("unable to clear  " + self.ID_name))

    def measure(self, channel):
        """
            define this method so any instrument has a defined method measure()        
        """
        return None


class InstrumentHub(QObject):
    """
        this class manages a list of instruments (that one would use for an 
        experiment)
        
    """

    def __init__(self, parent=None, debug=False, **kwargs):

        if parent != None:
            
            super(InstrumentHub, self).__init__(parent)
            self.parent = parent
            # connect with its parent to change the debug mode throught a
            # signal
            self.connect(parent, SIGNAL(
                "DEBUG_mode_changed(bool)"), self.set_debug_state)

        else:
            
            self.parent = None
            
        logging.info("InstrumentHub created")

        self.DEBUG = debug
        logging.debug("debug mode of InstrumentHub Object :%s" % (self.DEBUG))

        # this is an ordered dictionary where the keys are the port names
        # and the values are the Instrument objects (which should inherit from
        # Tool.MeasInstr and implement a measure(string) function)
        self.instrument_list = OrderedDict()

        # this will be the list of [GPIB address, parameter name] pairs
        # the read data command can then call instrument_list[port].measure param for
        # each element in this list
        self.port_param_pairs = []

        if INTF_PROLOGIX in kwargs:
            # the connection is passed as an argument

            if isinstance(kwargs[INTF_PROLOGIX], str):
                # it was the COM PORT number so we initiate an instance
                # of prologix controller
                if "COM" in kwargs[INTF_PROLOGIX]:
                    
                    self.prologix_com_port = utils.PrologixController(
                        kwargs[INTF_PROLOGIX])

            else:
                # it was the PrologixController instance
                self.prologix_com_port = kwargs[INTF_PROLOGIX]

                if "Prologix GPIB-USB Controller" in self.prologix_com_port.controller_id():
                    pass

                else:
                    logging.error(
                        "The controller passed as an argument is not the good one")

        else:
            # the connection doesn't exist so we create it
            self.prologix_com_port = utils.PrologixController()

    def __del__(self):
        self.clean_up()
        logging.info("InstrumentHub deleted")

    def connect_hub(self, instr_list, dev_list, param_list):
        """ 
            triggers the connection of a list of instruments instr_list,
            dev_list contains the port name information and param_list should
            refer to one of the parameters each instrument would measure
            
        """
        # first close the connections and clear the lists
        self.clean_up()

        for instr_name, device_port, param in zip(instr_list, dev_list, param_list):
            
            logging.debug("Connect_hub : Connecting %s to %s to measure %s" % (
                instr_name, device_port, param))
            self.connect_instrument(
                instr_name, device_port, param, send_signal=False)

            if self.parent != None:
                
                self.emit(SIGNAL("changed_list()"))
                
        print self.port_param_pairs
        print self.instrument_list
        
    def connect_instrument(self,instr_name,device_port,param,send_signal=True):
        #device_port should contain the name of the GPIB or the COM port
#        class_inst=__import__(instr_name)
#        logging.debug("Connect_intrument args : %s, %s, %s"%(instr_name,device_port,param))
        
        if __name__ == "__main__":
            
            class_inst = import_module(instr_name)

        else:
            class_inst=import_module("."+instr_name,package=utils.LABDRIVER_PACKAGE_NAME)
        
        if device_port in self.instrument_list:
            print 'Instrument already exists at' + device_port
            # Another data channel already used this instrument - make
            # sure it's the same type!!!
            if instr_name != self.instrument_list[device_port].ID_name:

                print("You are trying to connect " +
                      instr_name + " to the port " + device_port)
                print("But " + self.instrument_list[
                      device_port].ID_name + " is already connected to " + device_port)
                instr_name = 'NONE'
                send_signal = False

            else:
                print("Connect_instrument: added to %s at address %s measurement of %s" % (
                    instr_name, device_port, param))

        else:

            if instr_name != '' and instr_name != 'NONE':

                if class_inst.INTERFACE == INTF_PROLOGIX and self.prologix_com_port != None:
                    print("The instrument uses prologix")
                    obj = class_inst.Instrument(
                        device_port, self.DEBUG, prologix=self.prologix_com_port)

                elif class_inst.INTERFACE == INTF_PROLOGIX and self.prologix_com_port == None:
                    
                    logging.error(
                        "The interface is PROLOGIX but the controller object is not provided")

                else:
                    
                    obj = class_inst.Instrument(device_port, self.DEBUG)

                if not self.DEBUG:
                    
                    device_port = obj.resource_name

                self.instrument_list[device_port] = obj

                print("Connect_instrument: Connected %s to %s to measure %s" %
                      (instr_name, device_port, param))

        if instr_name != '' and instr_name != 'NONE':
            
            self.port_param_pairs.append([device_port, param])

        else:
            
            self.port_param_pairs.append([None, None])

        if send_signal:
            #            print "sending the signal"
            self.emit(SIGNAL("changed_list()"))

    def get_instrument_list(self):

        return self.instrument_list

    def get_port_param_pairs(self):
        """get the port name together with the associated parameter measured"""
        return self.port_param_pairs

    def get_instrument_nb(self):
        """get the number of instrument in the hub"""
        return len(self.port_param_pairs)

    def get_connectable_ports(self):
        """get the names of all ports on the computer that see an instrument"""
        return utils.list_serial_ports() +\
        self.prologix_com_port.get_open_gpib_ports() +\
        utils.list_GPIB_ports()

    def set_debug_state(self, state):
        """change the DEBUG property of the IntrumentHub instance"""
        self.DEBUG = state
        logging.debug("debug mode of InstrumentHub Object :%s" % (self.DEBUG))

    def clean_up(self):
        """ closes all instruments and reset the lists and dictionnaries """
        
        for key, inst in list(self.instrument_list.items()):

            if key:
                
                inst.close()

        self.instrument_list = {}
        self.port_param_pairs = []
        self.instrument_list[None] = None


class SimpleConnectWidget(QWidget):
    """
    this widget displays a combobox with a list of instruments which the
    user can connect to, it also has a refresh button
    """

    def __init__(self, parent=None):
        super(SimpleConnectWidget, self).__init__(parent)

        # main layout of the form is the verticallayout

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")

        # moved the script stuff to a separate widget that lives in the toolbar

        self.labelLayout = QHBoxLayout()
        self.labelLayout.setObjectName("labelLayout")

        self.portLabel = QLabel(self)
        self.portLabel.setText("Availiable Ports")
        self.instrLabel = QLabel(self)
        self.instrLabel.setText("Instruments")

        self.labelLayout.addWidget(self.portLabel)
        self.labelLayout.addWidget(self.instrLabel)

        self.verticalLayout.addLayout(self.labelLayout)

        self.ports = QComboBox(self)
        self.ports.addItems(refresh_device_port_list())
        self.ports.setObjectName("cbb_ports")

        self.instruments = QComboBox(self)
        self.instruments.addItems(utils.list_drivers(interface="real")[0])
        self.ports.setObjectName("cbb_instrs")

        self.cbbLayout = QHBoxLayout()
        self.cbbLayout.setObjectName("cbbLayout")

        self.cbbLayout.addWidget(self.ports)
        self.cbbLayout.addWidget(self.instruments)

        self.verticalLayout.addLayout(self.cbbLayout)

        self.connectButton = QPushButton(self)
        self.connectButton.setText("Connect the instrument")
        self.connectButton.setObjectName("connectButton")

        self.refreshButton = QPushButton(self)
        self.refreshButton.setText("refresh the port list")
        self.refreshButton.setObjectName("refreshButton")

        self.verticalLayout.addWidget(self.connectButton)
        self.verticalLayout.addWidget(self.refreshButton)
        self.headerTextEdit = QPlainTextEdit("")
        fontsize = self.headerTextEdit.fontMetrics()

        pal = QPalette()
        textc = QColor(245, 245, 240)
        pal.setColor(QPalette.Base, textc)
        self.headerTextEdit.setPalette(pal)
        # d3d3be
#        self.headerTextEdit.ba
        self.headerTextEdit.setFixedHeight(fontsize.lineSpacing() * 8)
        self.verticalLayout.addWidget(self.headerTextEdit)

        # moved the start stop button to the toolbar only

        self.setLayout(self.verticalLayout)

        self.connect(self.connectButton, SIGNAL(
            'clicked()'), self.on_connectButton_clicked)
        self.connect(self.refreshButton, SIGNAL(
            'clicked()'), self.on_refreshButton_clicked)

    def on_connectButton_clicked(self):
        """Connect a given instrument through a given port"""
        port = self.ports.currentText()
        instrument_name = self.instruments.currentText()

        # load the module which contains the instrument's driver
        if __name__ == "__main__":
            
            class_inst = import_module(instrument_name)
            
        else:
            
            class_inst = import_module(
                "." + instrument_name, package=utils.LABDRIVER_PACKAGE_NAME)
        msg = ""
#        msg.append("example")
#        msg.append("</span>")
        self.headerTextEdit.appendHtml(msg)
#        self.headerTextEdit.appendPlainText(msg)
        try:
            
            i = class_inst.Instrument(port)
            self.headerTextEdit.appendPlainText("%s" % (i.identify()))
            self.headerTextEdit.appendHtml(
                "The connection to the instrument %s through the port %s <span style=\" color:#009933;\" >WORKED</span>\n" % (instrument_name, port))

            i.close()
            
        except:
            
            self.headerTextEdit.appendHtml(
                "The connection to the instrument %s through the port %s <span style=\" color:#ff0000;\" >FAILED</span>\n" % (instrument_name, port))

    def on_refreshButton_clicked(self):
        """Refresh the list of the availiable ports"""
        self.ports.clear()
        self.ports.addItems(refresh_device_port_list())

# try to connect to all ports availiable and send *IDN? command
# this is something than can take some time


def whoisthere():
    
    if old_visa:
        
        port_addresses = visa.get_instruments_list()
        
    else:
        
        rm = visa.ResourceManager()
        port_addresses = rm.list_resources()

    connection_list = {}
    
    for port in port_addresses:
        
        try:
            
            print(port)
            device = MeasInstr(port)
            device.connection.timeout = 0.5
#            print port +" OK"
            try:
                
                name = device.identify()
                connection_list[port] = name
                
            except:
                
                pass

        except:
            
            pass
        
    return connection_list


def test_prologix_simple():
    import time
    ts = time.time()
    i = MeasInstr("GPIB0::7", interface=INTF_PROLOGIX)
    print(time.time() - ts)
    print(i.ask("*IDN?\n"))
    print(time.time() - ts)


def test_prologix_dual():
    import time
    ts = time.time()
    i = MeasInstr("GPIB0::7", interface=INTF_PROLOGIX)
    print(time.time() - ts)
    j = MeasInstr("GPIB0::12", interface=INTF_PROLOGIX, prologix=i.connection)
    print(time.time() - ts)
    print(i.ask("*IDN?\n"))
    print(time.time() - ts)
    print(j.ask("*IDN?\n"))
    print(time.time() - ts)


def test_prologix_Hub():

    h = InstrumentHub()  # prologix = PROLOGIX_COM_PORT)
    h.connect_hub(["CG500", "LS340", "PARO1000"],
                  ["GPIB0::7","GPIB0::12", "COM4"],
                  ["HeLevel", "A", "PRESSURE"]
                 )

    insts = h.get_instrument_list()

    for inst in insts:

        if inst != None:

            print insts[inst].identify()

    print(h.get_prologix_gpib_ports())


def test_hub_debug_mode():
    h = InstrumentHub()
    h.DEBUG = True
    h.connect_hub(['TIME', 'DICE', 'TIME'], [
                  '', 'COM14', ''], ['Time', 'Roll', 'dt'])

if __name__ == "__main__":

    #    test_prologix_dual()
    #    test_prologix_Hub()
    test_hub_debug_mode()
#    instr_hub=InstrumentHub(debug=True)

#    instr_hub.connect_hub(["CG500"],["COM1"],["HeLevel"])
#    i=MeasInstr('GPIB0::23::INSTR')
#    print i.identify()


#    from PyQt4.QtGui import QApplication
#    import sys
#    app = QApplication(sys.argv)
#    ex = SimpleConnectWidget()
#    ex.show()
#    sys.exit(app.exec_())

