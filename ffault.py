#!/usr/bin/env python

import sys
import os.path
import glob
from optparse import OptionParser
import json
import datetime
import shutil
import urllib2
import getpass
import subprocess
import math

#PDL command stuff
JARFILE = 'ProductClient.jar'
CONFIGFILE = 'config.ini'

#depending on whether user is "gavin" or "mhearne", choose one of these
DEVPDLPATH = '/Users/%s/ProductClient' % getpass.getuser()
PRODPDLPATH = '/Users/%s/Desktop/ProductClient' % getpass.getuser()

#default basemap caption
DEFAULT_CAPTION = """Surface projection of the slip distribution superimposed on GEBCO bathymetry. Thick white lines indicate major plate boundaries [Bird, 2003]. Gray circles, if present, are aftershock locations, sized by magnitude."""

#required size of the base map for web page
WEB_MAP_WIDTH = 304
#output name for web base map
OUTPUT_BASEMAP = 'basemap.png'

#depending on whether user is "gavin" or "mhearne", choose one of these
PRODCMD = "java -jar [JARFILE] --configFile=[CONFIGFILE] --send --source=us --type=finite-fault --code=[NET][EVENTCODE] --directory=[FFMDIR] --privateKey=/Users/%s/Desktop/ProductClient/id_dsa_ffm --trackerURL=http://ehppdl1.cr.usgs.gov/tracker/ --eventsource=[NET] --eventsourcecode=[EVENTCODE] [PROPERTIES]" % getpass.getuser()

DEVCMD = "java -jar [JARFILE] --configFile=[CONFIGFILE] --send --source=us --type=finite-fault --code=[NET][EVENTCODE] --directory=[FFMDIR] --eventsource=[NET] --eventsourcecode=[EVENTCODE] [PROPERTIES]"

#names of template html files
TEMPLATE1 = 'template1.html'
TEMPLATE2 = 'template2.html'

#folder where all pdl output should go
BASE_PDL_FOLDER = '/Users/%s/pdloutput/' % getpass.getuser()

#list of file patterns to copy from input folder(s) to output folder
FILE_PATTERNS = {'bodywave':'*bwave*.png',
                 'surfacewave':'*swave*.png',
                 'basemap':'*base*.png',
                 'moment':'mr.png',
                 'ge':'*ge*.png',
                 'slip':'*slip*.png',
                 'static':'*.param',
                 'cmt':'CMTSOLUTION',
                 'inp':'*.inp',
                 'kml':'*.kml',
                 'kmz':'*.kmz',
                 'fsp':'*.fsp',
                 'deformation':'*.disp',
                 'moment_text':'*.param'}

PROCESS_TEMPLATE_LONG = """We used GSN broadband waveforms downloaded from the NEIC waveform server.
We analyzed [XX] teleseismic broadband P waveforms, [YY] broadband SH waveforms, 
and [ZZ] long period surface waves selected based on data quality and azimuthal 
distribution. Waveforms are first converted to displacement by removing the 
instrument response and are then used to constrain the slip history using a finite 
fault inverse algorithm (Ji et al., 2002). We begin modeling using a hypocenter 
matching or adjusted slightly from the initial NEIC solution (Lon. = [AA] deg.; Lat. = 
[BB] deg., Dep. = [CC] km), and a fault plane defined using either the rapid W-Phase 
moment tensor (for near-real time solutions), or the gCMT moment tensor (for 
historic solutions)."""

PROCESS_TEMPLATE_NOLONG = """We used GSN broadband waveforms downloaded from the NEIC waveform
server.  We analyzed [XX] teleseismic broadband P waveforms and [YY]
broadband SH waveforms selected based on data quality and azimuthal
distribution. Waveforms are first converted to displacement by
removing the instrument response and are then used to constrain the
slip history using a finite fault inverse algorithm (Ji et al.,
2002). We begin modeling using a hypocenter matching or adjusted
slightly from the initial NEIC solution (Lon. = [AA] deg.; Lat. = [BB]
deg., Dep. = [CC] km), and a fault plane defined using either the
rapid W-Phase moment tensor (for near-real time solutions), or the
gCMT moment tensor (for historic solutions)."""

RESULT_TEMPLATE = """After comparing waveform fits based on the two planes of the input
moment tensor, we find that the nodal plane (strike= [DD] deg., dip= [EE]
deg.) fits the data better. The seismic moment release based upon this
plane is [FF] dyne.cm (Mw = [GG]) using a 1D crustal model interpolated
from CRUST2.0 (Bassin et al., 2000)."""

RESULT_TEMPLATE_SEGMENTS = """After comparing waveform fits based on the two planes of the input
moment tensor, we find that a solution adjusted from the nodal plane
striking towards [DD] deg. fits the data better. The adjusted solution
uses [HH] plane segments (see Table 1 below) designed to
match a priori knowledge of the fault (e.g., 3D slab geometry). The
seismic moment release based upon this solution is [FF] dyne.cm (Mw =
[GG]) using a 1D crustal model interpolated from CRUST2.0 (Bassin et
al., 2000).

<table border="1">
<tr><th>Segment</th><th>Strike (deg.)</th><th>Dip (deg.)</th></tr>
[SEGMENTS]
</table>
<br>
<i>Table 1. Multi-Segment Parameters.</i>
"""

CONTENTS = """<contents>
  <!-- Full listing of files -->

    <file title="Base Map" id="cmtsolution">
    <caption>
      <![CDATA[ Map of finite fault showing it's geographic context ]]>
    </caption>
    <format href="web[PLANE]/[EVENT]_basemap.png" type="image/png"/>
  </file>
  
  [BODYBLOCK]

  [SURFACEBLOCK]

  <file title="CMT Solution" id="cmtsolution">
    <caption>
      <![CDATA[ Full CMT solution for every point in finite fault region ]]>
    </caption>
    <format href="web[PLANE]/CMTSOLUTION" type="text/plain"/>
  </file>

  <file title="Inversion Parameters File 1" id="inpfile1">
    <caption>
      <![CDATA[ Basic inversion parameters for each node in the finite fault ]]>
    </caption>
    <format href="web[PLANE]/[EVENT].param" type="text/plain"/>
  </file>

  <file title="Inversion Parameters File 2" id="inpfile2">
    <caption>
      <![CDATA[ Complete inversion parameters for the finite fault, following the SRCMOD FSP format (http://equake-rc.info/) ]]>
    </caption>
    <format href="web[PLANE]/[EVENT].fsp" type="text/plain"/>
  </file>

  <file title="Coulomb Input File" id="coulomb">
    <caption>
      <![CDATA[ Format necessary for compatibility with Coulomb3 (http://earthquake.usgs.gov/research/software/coulomb/) ]]>
    </caption>
    <format href="web[PLANE]/[EVENT]_coulomb.inp" type="text/plain"/>
  </file>
  
  <file title="Moment Rate Function File" id="momentratefile">
    <caption>
      <![CDATA[ Ascii file of time vs. moment rate, used for plotting source time function ]]>
    </caption>
    <format href="web[PLANE]/[EVENT].param" type="text/plain"/>
  </file>

  <file title="Surface Deformation File" id="surfacedeformationfile">
    <caption>
      <![CDATA[ Surface displacement resulting from finite fault, calculated using Okada-style deformation codes ]]>
    </caption>
    <format href="web[PLANE]/[EVENT].disp" type="text/plain"/>
  </file>
</contents>"""

CONTENTSBODYBLOCK = """\n<file title="Body Waves Plot" id="bodywave[V]">
    <caption>
      <![CDATA[ Multi-panel plot showing body wave data from all contributing stations ]]>
    </caption>
    <format href="web[PLANE]/[EVENT]_bwave_[V].png" type="image/png"/>
  </file>"""

CONTENTSSURFACEBLOCK = """\n<!-- This will need to repeated for all surface wave files  -->
  <file title="Surface Waves Plot" id="surfacewave[V]">
    <caption>
      <![CDATA[ Multi-panel plot showing body wave data from all contributing stations ]]>
    </caption>
    <format href="web[PLANE]/[EVENT]_swave_[V].png" type="image/png"/>
  </file>\n"""

BODYBLOCK = """<img SRC="web/[EVENT]_bwave_[V].png"><br /><br />
<p>
Comparison of teleseismic body waves. Data are shown in black and synthetic seismograms 
are plotted in red. Both data and synthetic seismograms are aligned on the P or 
SH arrivals. The number at the end of each trace is the peak amplitude of the 
observation in micro-meters. The number above the beginning of each trace is 
the source azimuth; below is the epicentral distance. Shading describes relative 
weighting of the waveforms.
</p>
<hr />"""

BODYBLOCK1 = """<img SRC="web1/[EVENT]_bwave_[V].png"><br /><br />
<p>
Comparison of teleseismic body waves. Data are shown in black and synthetic seismograms 
are plotted in red. Both data and synthetic seismograms are aligned on the P or 
SH arrivals. The number at the end of each trace is the peak amplitude of the 
observation in micro-meters. The number above the beginning of each trace is 
the source azimuth; below is the epicentral distance. Shading describes relative 
weighting of the waveforms.
</p>
<hr />"""

BODYBLOCK2 = """<img SRC="web2/[EVENT]_bwave_[V].png"><br /><br />
<p>
Comparison of teleseismic body waves. Data are shown in black and synthetic seismograms 
are plotted in red. Both data and synthetic seismograms are aligned on the P or 
SH arrivals. The number at the end of each trace is the peak amplitude of the 
observation in micro-meters. The number above the beginning of each trace is 
the source azimuth; below is the epicentral distance. Shading describes relative 
weighting of the waveforms.
</p>
<hr />"""

SURFACEBLOCK = """<img SRC="web/[EVENT]_swave_[V].png"><br /><br />
<p>
Comparison of long period surface waves. Data are shown in black and synthetic 
seismograms are plotted in red. Both data and synthetic seismograms are aligned on 
the P or SH arrivals. The number at the end of each trace is the peak amplitude of 
the observation in micro-meters. The number above the beginning of each trace is 
the source azimuth and below is the epicentral distance. Shading describes relative 
weighting of the waveforms.
</p>
<hr />"""

SURFACEBLOCK1 = """<img SRC="web1/[EVENT]_swave_[V].png"><br /><br />
<p>
Comparison of long period surface waves. Data are shown in black and synthetic 
seismograms are plotted in red. Both data and synthetic seismograms are aligned on 
the P or SH arrivals. The number at the end of each trace is the peak amplitude of 
the observation in micro-meters. The number above the beginning of each trace is 
the source azimuth and below is the epicentral distance. Shading describes relative 
weighting of the waveforms.
</p>
<hr />"""

SURFACEBLOCK2 = """<img SRC="web2/[EVENT]_swave_[V].png"><br /><br />
<p>
Comparison of long period surface waves. Data are shown in black and synthetic 
seismograms are plotted in red. Both data and synthetic seismograms are aligned on 
the P or SH arrivals. The number at the end of each trace is the peak amplitude of 
the observation in micro-meters. The number above the beginning of each trace is 
the source azimuth and below is the epicentral distance. Shading describes relative 
weighting of the waveforms.
</p>
<hr />"""

HTMLFRAGMENT = """<div>
<p>[COMMENT]</p>
</div>"""

possiblelocs = ['/usr/bin','/bin','/usr/local/bin','/sw/bin',
                os.path.join(os.path.expanduser("~"),'bin'),
                '/home/shake/bin','/opt/local/bin','/opt/ImageMagick/bin/']

def findbinary(bin):
    """
    Search for binary in any of a list of likely locations on a Unix/Linux system.
    @param bin:  Name of binary to find ('ps2pdf','eps2pdf', etc.)
    """
    found = False
    binfile = None
    for p in possiblelocs:
        binfile = os.path.join(p,bin)
        if os.path.isfile(binfile):
            found = True
            break
        
    return binfile

def makeWebMap(webfolder):
    convertbin = findbinary('convert')
    if convertbin is None:
        return
    pdlfolder,web = os.path.split(os.path.abspath(webfolder))
    basemap = glob.glob(os.path.join(webfolder,'*_basemap.png'))
    if len(basemap):
        basemap = basemap[0]
    else:
        return
    output = os.path.join(pdlfolder,OUTPUT_BASEMAP)
    cmd = '%s %s -resize %ix %s' % (convertbin,basemap,WEB_MAP_WIDTH,output)
    output,retcode = getCommandOutput(cmd)

def createHTMLFragments(eventdicts,comment,pdlfolder):
    if len(comment.strip()):
        fragment = HTMLFRAGMENT.replace('[COMMENT]',comment)
        fragfile = os.path.join(pdlfolder,'comment.inc.html')
        f = open(fragfile,'wt')
        f.write(fragment)
        f.close()
    seq = 1
    for eventdict in eventdicts:
        if len(eventdicts) == 1:
            fragment = HTMLFRAGMENT.replace('[COMMENT]',eventdict['result'])
            fragfile = os.path.join(pdlfolder,'result%i.inc.html' % seq)
            f = open(fragfile,'wt')
            f.write(fragment)
            f.close()

        fragment = HTMLFRAGMENT.replace('[COMMENT]',eventdict['process'])
        fragfile = os.path.join(pdlfolder,'process%i.inc.html' % seq)
        f = open(fragfile,'wt')
        f.write(fragment)
        f.close()
        seq += 1
        
def getCommandOutput(cmd):
    """
    Internal method for calling external command.
    @param cmd: String command ('ls -l', etc.)
    @return: Two-element tuple containing a boolean indicating success or failure, 
    and the output from running the command.
    """
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdout=subprocess.PIPE,
                            )
    output = proc.communicate()[0]
    retcode = proc.returncode
    if retcode == 0:
        retcode = True
    else:
        retcode = False
    
    return (retcode,output)

def generateCmdLine(eventdicts,eventid,output):
    net = eventid[0:2]
    eventcode = eventid[2:]
    props = []
    ec = 1
    for eventdict in eventdicts:
        for key,value in eventdict.iteritems():
            if key in ['process','result']:
                continue
            props.append('--property-%s%i=%s' % (key,ec,str(value)))
        ec += 1
    propstr = ' '.join(props)
    if getpass.getuser() == 'mhearne':
        PDLPATH = DEVPDLPATH
        CMD = DEVCMD
    else:
        PDLPATH = PRODPDLPATH
        CMD = PRODCMD
    jar = os.path.join(PDLPATH,JARFILE)
    cfg = os.path.join(PDLPATH,CONFIGFILE)
    cmd = CMD.replace('[JARFILE]',jar)
    cmd = cmd.replace('[CONFIGFILE]',cfg)
    cmd = cmd.replace('[EVENTCODE]',eventcode)
    cmd = cmd.replace('[NET]',net)
    cmd = cmd.replace('[FFMDIR]',output)
    cmd = cmd.replace('[PROPERTIES]',propstr)
    return cmd

def createContents(eventid,outdir,bodywaves1,bodywaves2,surfacewaves1,surfacewaves2):
    eventcode = eventid[2:]
    bodytext = ''
    #determine whether we're in a single or double plane situation
    plane1 = '1'
    plane2 = '2'
    if not len(bodywaves2):
        plane1 = ''
    for fname in bodywaves1:
        fbase,fext = os.path.splitext(fname)
        parts = fbase.split('_')
        sequence = parts[-1]
        block = CONTENTSBODYBLOCK.replace('[EVENT]',eventcode)
        block = block.replace('[V]',sequence)
        block = block.replace('[PLANE]',plane1)
        bodytext += block
    for fname in bodywaves2:
        fbase,fext = os.path.splitext(fname)
        parts = fbase.split('_')
        sequence = parts[-1]
        block = CONTENTSBODYBLOCK.replace('[EVENT]',eventcode)
        block = block.replace('[V]',sequence)
        block = block.replace('[PLANE]',plane2)
        bodytext += block
    surfacetext = ''
    for fname in surfacewaves1:
        fbase,fext = os.path.splitext(fname)
        parts = fbase.split('_')
        sequence = parts[-1]
        block = CONTENTSSURFACEBLOCK.replace('[EVENT]',eventcode)
        block = block.replace('[V]',sequence)
        block = block.replace('[PLANE]',plane1)
        surfacetext += block
    for fname in surfacewaves2:
        fbase,fext = os.path.splitext(fname)
        parts = fbase.split('_')
        sequence = parts[-1]
        block = CONTENTSSURFACEBLOCK.replace('[EVENT]',eventcode)
        block = block.replace('[V]',sequence)
        block = block.replace('[PLANE]',plane2)
        surfacetext += block

    
    contents = CONTENTS.replace('[BODYBLOCK]',bodytext)
    contents = contents.replace('[PLANE]',plane1)
    contents = contents.replace('[SURFACEBLOCK]',surfacetext)
    contents = contents.replace('[EVENT]',eventcode)
    cfile = os.path.join(outdir,'contents.xml')
    f = open(cfile,'wt')
    f.write(contents)
    f.close()
    

def getWavePlots(ffmdir):
    bodyfiles = glob.glob(os.path.join(ffmdir,FILE_PATTERNS['bodywave']))
    surfacefiles = glob.glob(os.path.join(ffmdir,FILE_PATTERNS['surfacewave']))
    return (bodyfiles,surfacefiles)

def fillHTML(eventdict,htmldata,comment,eventcode,bodyfiles,surfacefiles,version,caption,onePlane=True,planeNumber=1):
    location = getLocation(eventdict['lat'],eventdict['lon'])
    htmldata = htmldata.replace('[DATE]',eventdict['time'].strftime('%b %d, %Y'))
    htmldata = htmldata.replace('[MAG]','%.1f' % eventdict['magnitude'])
    htmldata = htmldata.replace('[LOCATION]','%s' % location)
    htmldata = htmldata.replace('[PROCESS]','%s' % eventdict['process'])
    htmldata = htmldata.replace('[RESULT]','%s' % eventdict['result'])
    htmldata = htmldata.replace('[EVENT]','%s' % eventcode)
    htmldata = htmldata.replace('[COMMENT]','%s' % comment)
    htmldata = htmldata.replace('[BASEMAP_CAPTION]','%s' % caption)
    if version == 1:
        htmldata = htmldata.replace('[STATUS]','Preliminary')
    else:
        htmldata = htmldata.replace('[STATUS]','Updated')
    htmldata = htmldata.replace('[VERSION]',str(version))
    if not onePlane:
      magnitude = (math.log10(eventdict['moment'])-16.1)/1.5
      htmldata = htmldata.replace('[MOMENT%i]' % planeNumber,'%.3g' % eventdict['moment'])
      htmldata = htmldata.replace('[MWMAG%i]' % planeNumber,'%.1f' % magnitude)
      htmldata = htmldata.replace('[STRIKE%i]' % planeNumber,'%.1f' % eventdict['strike1'])
      htmldata = htmldata.replace('[DIP%i]' % planeNumber,'%.1f' % eventdict['dip1'])
      htmldata = htmldata.replace('[RAKE%i]' % planeNumber,'%.1f' % eventdict['rake1'])
      bodytext = ''
      for bodyfile in bodyfiles:
          fpath,fname = os.path.split(bodyfile)
          fbase,fext = os.path.splitext(fname)
          parts = fbase.split('_')
          sequence = parts[-1]
          if planeNumber == 1:
              block = BODYBLOCK1
          else:
              block = BODYBLOCK2
          bodyblock = block.replace('[V]',sequence)
          bodyblock = bodyblock.replace('[EVENT]',eventcode)
          bodytext += bodyblock
      htmldata = htmldata.replace('[BODYBLOCK%i]' % planeNumber,bodytext)
      surfacetext = ''
      for surfacefile in surfacefiles:
          fpath,fname = os.path.split(surfacefile)
          fbase,fext = os.path.splitext(fname)
          parts = fbase.split('_')
          sequence = parts[-1]
          if planeNumber == 1:
              block = SURFACEBLOCK1
          else:
              block = SURFACEBLOCK2
          surfaceblock = block.replace('[V]',sequence)
          surfaceblock = surfaceblock.replace('[EVENT]',eventcode)
          surfacetext += surfaceblock
      htmldata = htmldata.replace('[SURFACEBLOCK%i]' % planeNumber,surfacetext)
    else:
        bodytext = ''
        for bodyfile in bodyfiles:
            fpath,fname = os.path.split(bodyfile)
            fbase,fext = os.path.splitext(fname)
            parts = fbase.split('_')
            sequence = parts[-1]
            bodyblock = BODYBLOCK.replace('[V]',sequence)
            bodyblock = bodyblock.replace('[EVENT]',eventcode)
            bodytext += bodyblock
        htmldata = htmldata.replace('[BODYBLOCK]',bodytext)
        surfacetext = ''
        for surfacefile in surfacefiles:
            fpath,fname = os.path.split(surfacefile)
            fbase,fext = os.path.splitext(fname)
            parts = fbase.split('_')
            sequence = parts[-1]
            surfaceblock = SURFACEBLOCK.replace('[V]',sequence)
            surfaceblock = surfaceblock.replace('[EVENT]',eventcode)
            surfacetext += surfaceblock
        htmldata = htmldata.replace('[SURFACEBLOCK]',surfacetext)
        
        
    return htmldata

def getLocation(lat,lon):
    MAX_DIST = 300
    urlt = 'http://igskcicgasordb2.cr.usgs.gov:8080/gs_dad/get_gs_info?latitude=LAT&longitude=LON&utc=UTC';
    url = urlt.replace('LAT','%.4f' % lat)
    url = url.replace('LON','%.4f' % lon)
    url = url.replace('UTC',datetime.datetime.utcnow().strftime('%m/%d/%Y:%H:%M:%S'))
    try:
        fh = urllib2.urlopen(url)
        content = fh.read()
        fh.close()
        data = json.loads(content)
        if data['cities'][0]['distance'] <= MAX_DIST:
            dist = data['cities'][0]['distance']
            direc = data['cities'][0]['direction']
            cname = data['cities'][0]['name']
            locstr = '%i km %s of %s' % (dist,direc,cname)
            return locstr
        try:
            locstr = data['fe']['longName']
            return locstr
        except:
            dist = data['cities'][0]['distance']
            direc = data['cities'][0]['direction']
            cname = data['cities'][0]['name']
            locstr = '%i km %s of %s' % (dist,direc,cname)
            return locstr
    except:
        locstr = '%.4f,%.4f' % (lat,lon)

    return locstr

def countWaves(wavefile):
    lines = open(wavefile,'rt').readlines()
    nt = int(lines[4].strip())
    ns = 0
    np = 0
    #read the int value of the 8th column of each line.  if greater than 2, increment ns, otherwise increment np
    for i in range(5,nt):
        parts = lines[i].split()
        if float(parts[8]) > 2:
            ns += 1
        else:
            np += 1
    return (np,ns)

def readMulti(eventfile):
    """
    2015 3 29 23 #date hour
    255.16 20.26 83.16 2.47e+20 #??
    -4.8812 152.5964 2015 3 29 23 #lat lon year month day hour (again)
    0.2 10 0
    1 1 5
    2.5
    3 9 6 #number of segments, line 7
    1
    30 255 83 1 # dip strike ? ? for segment 1 (line 9)
    17 5 0
    9 1 1 41 #line 11, ? ? ? depth
    2
    25 255 83 1 # dip strike ? ? for segment 2 on line (segment number * 6) + 1
    17 5 0
    9 6
    1 1 1 1 1
    1 6 1 1
    3
    20 255 83 1 #dip strike ? ? for segment 3 on line (segment number * 6) + 1
    17 10 0
    9 16
    2 1 1 1 1
    1 11 1 1
    """
    eventdict = {}
    lines = open(eventfile,'rt').readlines()
    #date/time info is in the first line of this file
    tparts = [int(p) for p in lines[0].split()] #list of integers: year, month, day, hour
    eventdict['time'] = datetime.datetime(tparts[0],tparts[1],tparts[2],tparts[3],0,0)
    #lat/lon is in the 3rd line of this file
    gparts = lines[2].split()
    eventdict['lat'] = float(gparts[0])
    eventdict['lon'] = float(gparts[1])
    #the flag for multiple segments of one plane is found in the 7th line of this file
    gparts = lines[6].split()
    eventdict['numsegments'] = int(gparts[0])
    #depth is in the 11th line in this file
    dparts = lines[10].split()
    eventdict['depth'] = float(dparts[3])
    #first dip and strike are on line 9
    dip1,strike1,rake1,tmp2 = [float(x) for x in lines[8].split()]
    eventdict['dip1'] = dip1
    eventdict['strike1'] = strike1
    eventdict['rake1'] = rake1
    if eventdict['numsegments'] > 1:
        for i in range(1,eventdict['numsegments']):
            lineno = (i+1)*6
            dip,strike,rake,tmp = [float(x) for x in lines[lineno].split()]
            keydip = 'dip%i' % (i+1)
            keystrike = 'strike%i' % (i+1)
            keyrake = 'rake%i' % (i+1)
            eventdict[keydip] = dip
            eventdict[keystrike] = strike
            eventdict[keyrake] = rake
    return eventdict
    
def getEventInfo(inputfolder):
    eventdict = {}
    eventfile = os.path.join(inputfolder,'Event_mult.in')
    plotfile = os.path.join(inputfolder,'plot_info')
    wavefile = os.path.join(inputfolder,'Readlp.das')
    lowfile = os.path.join(inputfolder,'synm.str_low')
    tmpdict = readMulti(eventfile)
    eventdict.update(tmpdict)
    
    #strike dip and rake are in the first line of this file
    lines = open(plotfile,'rt').readlines()
    mparts = lines[0].split()
    eventdict['moment'] = float(mparts[3])
    #moment magnitude is in the last line of this file
    eventdict['magnitude'] = float(lines[-1].strip())
    np,ns = countWaves(wavefile)
    if os.path.isfile(lowfile):
        nlow = int(open(lowfile,'rt').readline().strip())
    else:
        nlow = 0
    eventdict['nump'] = np
    eventdict['nums'] = ns
    eventdict['npsh'] = int((np+ns)/30.0+0.9999)
    eventdict['numlow'] = nlow
    eventdict['nplow'] = int(nlow/20+0.9999)
    return eventdict

def copyFiles(inputfolder,outputfolder):
    for key,pattern in FILE_PATTERNS.iteritems():
        pat = os.path.join(inputfolder,pattern)
        copyfiles = glob.glob(pat)
        for cfile in copyfiles:
            shutil.copy(cfile,outputfolder)

def makeTextBlocks(eventdicts):
    textdicts = {}
    eventcounter = 0
    for eventdict in eventdicts:
        if eventdict['numlow']:
            process = PROCESS_TEMPLATE_LONG
        else:
            process = PROCESS_TEMPLATE_NOLONG
        process = process.replace('[XX]','%i' % eventdict['nump'])
        process = process.replace('[YY]','%i' % eventdict['nums'])
        if eventdict['numlow']:
            process = process.replace('[ZZ]','%i' % eventdict['numlow'])
        process = process.replace('[AA]','%.1f' % eventdict['lon'])
        process = process.replace('[BB]','%.1f' % eventdict['lat'])
        process = process.replace('[CC]','%.1f' % eventdict['depth'])
        eventdict['process'] = process

        #fill in the paragraph describing the result for a single plane solution
        if eventdict['numsegments'] == 1:
            result = RESULT_TEMPLATE
        else:
            result = RESULT_TEMPLATE_SEGMENTS
            segment_template = '<tr><td>[NUM]</td><td>[DD]</td><td>[EE]</td></tr>\n'
            segmentstr = ''
            for i in range(0,eventdict['numsegments']):
                segtemp = segment_template
                segnum = i+1
                ddkey = 'strike%i' % (segnum)
                eekey = 'dip%i' % (segnum)
                segtemp = segtemp.replace('[NUM]','%i' % segnum)
                segtemp = segtemp.replace('[DD]','%.1f' % eventdict[ddkey])
                segtemp = segtemp.replace('[EE]','%.1f' % eventdict[eekey])
                segmentstr += segtemp
            result = result.replace('[SEGMENTS]',segmentstr)
        result = result.replace('[DD]','%.1f' % eventdict['strike1'])
        result = result.replace('[EE]','%.1f' % eventdict['dip1'])
        result = result.replace('[FF]','%.1e' % eventdict['moment'])
        result = result.replace('[GG]','%.1f' % eventdict['magnitude'])
        result = result.replace('[HH]','%i' % eventdict['numsegments'])
        eventdict['result'] = result

    return eventdicts

if __name__ == '__main__':
    usage = """usage: %prog [options] NET EVENTID FFMDIR1 [FFMDIR2]
    Use this script to send finite fault data to PDL.
    Example: (for a single plane solution)
    %prog us b0006bqc /home/ghayes/ffmdata/b0006bqc
    OR (for a double plane solution)
    %prog us b0006bqc /home/ghayes/ffmdata/b0006bqc /home/ghayes/ffmdata/b0006bqc2
    OR (single plane solution with comment)
    %prog us b0006bqc /home/ghayes/ffmdata/b0006bqc /home/ghayes/ffmdata/b0006bqc2 -c"This earthquake is very deadly."

    Note: It is possible to modify the caption for the basemap by creating a file called basemap_caption.txt
    in the finite fault directory (or in the case where there are two, in either one).  This file should contain
    the desired caption for the basemap image.  If no such file is found, then the caption will read:

    "Surface projection of the slip distribution superimposed on GEBCO bathymetry. Red lines indicate major plate boundaries [Bird, 2003]. Gray circles, if present, are aftershock locations, sized by magnitude."
    
    """
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--comment", dest="comment",
                      help="add a 'scientific analysis' comment to the HTML output", metavar="COMMENT")
    parser.add_option("-v", "--version", dest="version",
                      help="Add a version number to the finite fault output", metavar="COMMENT")
    parser.add_option("-r", "--review",action="store_true",
                      dest="doReview",default=False,help="don't send products to PDL")
    (options, args) = parser.parse_args()
    homedir = os.path.dirname(os.path.abspath(__file__)) #where is this script?
    html1 = os.path.join(homedir,TEMPLATE1)
    html2 = os.path.join(homedir,TEMPLATE2)
    if not os.path.isfile(html1) or not os.path.isfile(html2):
      
        print 'Missing either or both of the HTML template files: %s, %s.' % (html1,html2)
        parser.print_help()
        sys.exit(1)

    if not len(args):
        print 'Missing input arguments.'
        parser.print_help()
        sys.exit(0)

    comment = 'Not available yet.'
    if options.comment is not None:
        comment = options.comment
    if options.version is None:
        version = 1
    else:
        try:
            version = int(options.version)
            if version < 1:
                raise Exception
        except:
            print 'Weird version number "%s". Exiting.' % options.version

    net = args[0]
    eventcode = args[1]
    eventid = net+eventcode
    pdlfolder = os.path.join(BASE_PDL_FOLDER,eventid)
    
    if len(args) == 3:
        bodyfiles2 = []
        surfacefiles2 = []
        ffmdir = args[2]
        #copy the files first
        webfolder = os.path.join(pdlfolder,'web')
        if not os.path.isdir(webfolder):
            os.makedirs(webfolder)
        copyFiles(ffmdir,webfolder)
        eventdict = getEventInfo(ffmdir)
        eventdict = makeTextBlocks([eventdict])[0]
        htmloutfile = os.path.join(pdlfolder,'%s.html' % eventcode)
        htmldata = open(html1,'rt').read()
        bodyfiles1,surfacefiles1 = getWavePlots(ffmdir)

        #if there is a basemap_caption.txt file present, read in that text and insert it
        #into the HTML in [BASEMAP_CAPTION] macro
        captionfile = os.path.join(ffmdir,'basemap_caption.txt')
        if os.path.isfile(captionfile):
            caption = open(captionfile,'rt').read()
        else:
            caption = DEFAULT_CAPTION
        
        htmldata = fillHTML(eventdict,htmldata,comment,eventcode,bodyfiles1,surfacefiles1,version,caption)
        makeWebMap(webfolder)
        f = open(htmloutfile,'wt')
        f.write(htmldata)
        f.close()
        createHTMLFragments([eventdict],comment,pdlfolder)
    else:
        ffmdir1 = args[2]
        ffmdir2 = args[3]

        #if there is a basemap_caption.txt file present in either folder, read in that text and insert it
        #into the HTML in [BASEMAP_CAPTION] macro
        captionfile1 = os.path.join(ffmdir1,'basemap_caption.txt')
        captionfile2 = os.path.join(ffmdir2,'basemap_caption.txt')
        if os.path.isfile(captionfile1):
            caption = open(captionfile1,'rt').read()
        elif os.path.isfile(captionfile2):
            caption = open(captionfile2,'rt').read()
        else:
            caption = DEFAULT_CAPTION
        
        #first plane
        #copy the files first
        webfolder1 = os.path.join(pdlfolder,'web1')
        if not os.path.isdir(webfolder1):
            os.makedirs(webfolder1)
        copyFiles(ffmdir1,webfolder1)
        eventdict1 = getEventInfo(ffmdir1)
        eventdict1 = makeTextBlocks([eventdict1])[0]
        htmloutfile = os.path.join(pdlfolder,'%s.html' % eventcode)
        htmldata = open(html2,'rt').read()
        bodyfiles1,surfacefiles1 = getWavePlots(ffmdir1)
        htmldata = fillHTML(eventdict1,htmldata,comment,eventcode,bodyfiles1,surfacefiles1,version,caption,onePlane=False,planeNumber=1)
        makeWebMap(webfolder1)
        #second plane
        #copy the files first
        webfolder2 = os.path.join(pdlfolder,'web2')
        if not os.path.isdir(webfolder2):
            os.makedirs(webfolder2)
        copyFiles(ffmdir2,webfolder2)
        eventdict2 = getEventInfo(ffmdir2)
        eventdict2 = makeTextBlocks([eventdict2])[0]
        bodyfiles2,surfacefiles2 = getWavePlots(ffmdir2)
        htmldata = fillHTML(eventdict2,htmldata,comment,eventcode,bodyfiles2,surfacefiles2,version,caption,onePlane=False,planeNumber=2)
        #write out the html data
        f = open(htmloutfile,'wt')
        f.write(htmldata)
        f.close()
        createHTMLFragments([eventdict1,eventdict2],comment,pdlfolder)
    createContents(eventid,pdlfolder,bodyfiles1,bodyfiles2,surfacefiles1,surfacefiles2)
    if not options.doReview:
        if len(args) > 3:
            cmd = generateCmdLine([eventdict1,eventdict2],eventid,pdlfolder)
        else:
            cmd = generateCmdLine([eventdict],eventid,pdlfolder)
        retcode,output = getCommandOutput(cmd)
        print 'Command "%s" returned %s with output: "%s"' % (cmd,retcode,output)
    else:
        print 'Output was written to %s' % pdlfolder
        

            
        
        
        
    
    
    
    
