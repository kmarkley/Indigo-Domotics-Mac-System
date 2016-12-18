#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################################################################################
"""
    Mac OS System plug-in interface module
    By Bernard Philippe (bip.philippe) (C) 2015

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.#
"""
####################################################################################

import indigo
import time
from bipIndigoFramework import core
from bipIndigoFramework import osascript
from bipIndigoFramework import shellscript
import re
# a little future-proofing:
try:
    from shlex import quote as cmd_quote
except ImportError:
    from pipes import quote as cmd_quote


# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

_repProcessStatus = re.compile(r" *([0-9]+) +(.).+$")
_repProcessData = re.compile(r"(.+?)  +([0-9.,]+) +([0-9.,]+) +(.+)$")
_repVolumeData2 = re.compile(r".+? [0-9]+ +([0-9]+) +([0-9]+) .+")
_repVolumeData3 = re.compile(r".+? ([0-9\.]+[A-Z]) +([0-9\.]+[A-Z]) +([0-9\.]+[A-Z]) +([0-9]+%) .+")

# change smb to smbfs, but also throw an error if mount command doesn't support filesystem
_fileSystems = {u'smb':u'smbfs',u'nfs':u'nfs',u'afp':u'afp',u'ftp':u'ftp',u'webdav':u'webdav'}

def init():
    osascript.init()
    shellscript.init()


##########
# Application device
########################
pStatusDict ={'I':u'idle','R':u'running', 'S':u'running', 'T':u'stopped', 'U':u'waiting', 'Z':u'zombie' }

def getProcessStatus(thedevice, thevaluesDict):
    """ Searches for the task in system tasklist and returns onOff states

        Args:
            thedevice: current device
            thevaluesDict: dictionary of the status values so far
        Returns:
            success: True if success, False if not
            thevaluesDict updated with new data if success, equals to the input if not
    """
    pslist = shellscript.run(u"ps -awxc -opid,state,args | egrep %s" % (cmd_quote(u' ' + thedevice.pluginProps[u'ApplicationProcessName']+u'$')),_repProcessStatus,[u'ProcessID',u'PStatus'])

    if pslist[u'ProcessID']==u'':
        thevaluesDict[u'onOffState']=False
        thevaluesDict[u'ProcessID']=0
        thevaluesDict[u'PStatus']="off"
    else:
        thevaluesDict[u'onOffState']=True
        thevaluesDict.update(pslist)
        # special update for process status
        thevaluesDict[u'PStatus']= pStatusDict[thevaluesDict[u'PStatus']]

    return (True,thevaluesDict)

def getProcessData(thedevice, thevaluesDict):
    """ Searches for the task in system tasklist and returns states data

        Args:
            thedevice: current device
            thevaluesDict: dictionary of the status values so far
        Returns:
            success: True if success, False if not
            thevaluesDict updated with new data if success, equals to the input if not
    """
    pslist = shellscript.run(u"ps -wxc -olstart,pcpu,pmem,etime -p%s | sed 1d" % (thevaluesDict[u'ProcessID']),_repProcessData,[u'LStart','PCpu','PMem','ETime'])

    if pslist[u'LStart']=='':
        thevaluesDict[u'onOffState']=False
        thevaluesDict[u'ProcessID']=0
        thevaluesDict[u'PStatus']="off"
        thevaluesDict[u'LStart']=""
        thevaluesDict[u'ETime']=0
        thevaluesDict[u'PCpu']=0
        thevaluesDict[u'PMem']=0
    else:
        thevaluesDict.update(pslist)
        # special update for ellapsed time : convert to seconds
        try:
            (longday,longtime)=thevaluesDict[u'ETime'].split('-')
        except:
            longtime=thevaluesDict[u'ETime']
            longday=0
        try:
        	(longh,longm,longs)=longtime.split(':')
        except:
        	(longm,longs)=longtime.split(':')
        	longh=0
		thevaluesDict[u'ETime']= ((int(longday)*24 + int(longh))*60 + int(longm))*60 + int(longs)

    return (True,thevaluesDict)

##########
# Volume device
########################
def getVolumeStatus(thedevice, thevaluesDict):
    """ Searches for the volume to return states OnOff only

        Args:
            thedevice: current device
            thevaluesDict: dictionary of the status values so far
        Returns:
            success: True if success, False if not
            thevaluesDict updated with new data if success, equals to the input if not
    """
    # check if mounted
    if thedevice.deviceTypeId  == u'bip.ms.volume':
        theScript = u"ls -1 /Volumes | grep %s" % (cmd_quote(u'^'+thedevice.pluginProps[u'VolumeID']+u'$'))
    elif thedevice.deviceTypeId  == u'bip.ms.nas':
        theScript = u"/bin/df -Hn | grep %s" % (cmd_quote(u"/Volumes/"+thedevice.pluginProps[u'VolumeID']+u'$'))

    if shellscript.run(theScript)>'':
        thevaluesDict[u'onOffState']=True
        thevaluesDict[u'VStatus']="on"
    else:
        thevaluesDict[u'onOffState']=False
    
    return (True,thevaluesDict)

def getVolumeData(thedevice, thevaluesDict):
    """ Searches for the volume using system diskutil and df to return states data

        Args:
            thedevice: current device
            thevaluesDict: dictionary of the status values so far
        Returns:
            success: True if success, False if not
            thevaluesDict updated with new data if success, equals to the input if not
        """
    if thedevice.deviceTypeId  == u'bip.ms.volume':
        pslist = shellscript.run(u"/usr/sbin/diskutil list | grep %s" % (cmd_quote(u' '+thedevice.pluginProps[u'VolumeID']+u'  ')),[(6,32),(68,-1)],[u'VolumeType',u'VolumeDevice'])
        dfGrepTerm = u'^/dev/%s' % (pslist[u'VolumeDevice'])
    elif thedevice.deviceTypeId  == u'bip.ms.nas':
        pslist = {u'VolumeType': _fileSystems[thedevice.pluginProps[u'VolumeURL'].split(':')[0]], u'VolumeDevice': thedevice.pluginProps['VolumeURL']}
        dfGrepTerm = '/Volumes/%s$' % (thedevice.pluginProps[u'VolumeID'])
    
    if pslist[u'VolumeDevice']=='':
        thevaluesDict[u'onOffState']=False
        thevaluesDict[u'VStatus']=u'off'
    else:
        thevaluesDict.update(pslist)
        # find free space
        pslist = shellscript.run(u"/bin/df -Hn | grep %s" % (cmd_quote(dfGrepTerm)),_repVolumeData3,[u'Size',u'Used',u'Available',u'Capacity'])
        if pslist[u'Used'] !=u'':
            indigo.server.log(pslist[u'Used'])
            thevaluesDict[u'VolumeSize'] = pslist[u'Size'] 
            thevaluesDict[u'pcUsed']= int(pslist[u'Capacity'][:-1])
            thevaluesDict[u'onOffState']=True
            thevaluesDict[u'VStatus']=u'on'
        else:
            thevaluesDict[u'onOffState']=False
            thevaluesDict[u'VStatus']=u'notmounted'
            if thedevice.deviceTypeId  == u'bip.ms.nas':
                shellscript.run(u"/bin/rmdir %s 2>/dev/null" % (cmd_quote(u"/Volumes/"+thedevice.pluginProps[u'VolumeID'])))

    return (True,thevaluesDict)


def spinVolume(thedevice, thevaluesDict):
    """ Touch a file to keep the disk awaken

        Args:
            thedevice: current device
            thevaluesDict: dictionary of the status values so far
        Returns:
            success: True if success, False if not
            thevaluesDict updated with new data if success, equals to the input if not
        """

    if (thedevice.states[u'VStatus']==u'on') and (thedevice.pluginProps[u'keepAwaken']):
        psvalue = shellscript.run(u"touch %s" % (cmd_quote(u'/Volumes/'+thedevice.pluginProps[u'VolumeID']+u'/.spinner')))
        if psvalue is None:
            return (False, thevaluesDict)
        else:
            thevaluesDict[u'LastPing']=time.strftime('%c',time.localtime())
    return (True, thevaluesDict)

