#!/usr/bin/env python
"""
Copyright 2017 ARC Centre of Excellence for Climate Systems Science

author: Paola Petrelli <paola.petrelli@utas.edu.au>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

 This script is used to download, checksum and update the TRMM dataset on
   NCI server raijin
 dataset is in /g/data1/ua8/NASA_TRMM
 scripts and checksums files are currently in /g/data1/ua8/Download/NASA_TRMM
 Last change:
      2017-05-24

 Usage:
 Inputs are:
   y - year to check/download/update the only one required
   c - to indicate that year is current, 
       this will call the download_dir function first,
       to check if there are new files to download 
   f - this forces local chksum to be re-calculated even if local file exists
 The script will look for the local and remote checksum files:
     trmm_<local/remote>_cksum_<year>.txt
 If the local file does not exists calls calculate_cksum() to create one
 If the remote cksum file does not exist calls retrieve_cksum() to create one
 The remote checksum are retrieved directly from the cksum field in 
   the filename.xml available online.
 The checksums are compared for each files and if they are not matching 
   the local file is deleted and download it again using the requests module
 The requests module also handle the website cookies by opening a session
   at the start of the script
 
 Uses the following modules:
 import requests to download files and html via http
 import beautifulsoup4 to parse html
 import xml.etree.cElementTree to read a single xml field
 import time and calendar to convert timestamp in filename
        to day number from 1-366 for each year
 import subprocess to run cksum as a shell command
 import argparse to manage inputs 
 should work with both python 2 and 3

"""

from __future__ import print_function

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
import os, sys
import time, calendar
import argparse
import subprocess
import requests
from bs4 import BeautifulSoup
import re


def parse_input():
    ''' Parse input arguments '''
    parser = argparse.ArgumentParser(description='''Retrieve checksum value for the TRMM HDF 
             files directly from TRMM http server using xml.etree to read the corresponding field. 
             Usage: python TRMM-xml.py -y <year>  ''', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-y','--year', type=int, help='year to process', required=True)
    parser.add_argument('-c','--current', help='current year, download always first',
                        action='store_true', required=False)
    parser.add_argument('-f','--force', help='force local cheksum calculation even if file is present',
                        action='store_true', required=False)
    return vars(parser.parse_args())


def retrieve_xml(hdf_list,fremote):
    ''' extract from the online xml files the checksums and save them to a file
        input: hdf_list a list of all the HDF files in the "year" directory '''
    global http_url, session
    dremote={}
    # from each filename derived the complete url for the corresponding XML file online
    # access Checksum from xml field CheckSumValue and save to file
    for fhdf in hdf_list:
        fyr,fday = get_tstamp(fhdf)
        #tree = ET.fromstring(urllopen("/".join([http_url,fyr,fday,fhdf+".xml"])).read())
        tree = ET.fromstring(session.get("/".join([http_url,fyr,fday,fhdf+".xml"])).content)
        for elem in tree.iter():
            if elem.tag == 'CheckSumValue':
                fremote.write(fhdf + " " + elem.text + "\n") 
                dremote[fhdf]=elem.text
    return dremote
        

def get_tstamp(fname):
    '''from each filename derive from the time stamp, year and day string'''
    global yr, syr
    tstamp=fname.split(".")[1]
    hour=fname.split(".")[2]
    iday = time.strptime(tstamp, "%Y%m%d").tm_yday
    # 00 hour is stored in previous day directory!
    fyr=syr
    if hour == "00":
       iday = iday - 1
       if iday == 0:
           fyr= str(yr-1)
           iday=365
           if calendar.isleap(yr-1):
               iday=366
    fday = str(iday).zfill(3)
    return fyr, fday


def calculate_cksum(hdf_list,flocal):
    ''' calculate cksum for local files for year '''
    dlocal={}
    for fhdf in hdf_list: 
        p = subprocess.Popen("cksum "+fhdf, stdout=subprocess.PIPE, shell=True)
        (output, err) = p.communicate()
        dlocal[fhdf] = output.split(" ")[0]
        flocal.write(output) 
    return dlocal
    

def read_sums(fopen,kind):
    ''' read checksum values for checksum files from respective yearly files '''
    dresult={}
    for l in fopen.readlines():
        bits = l.replace("\n","").split(" ")
        if kind=='local': dresult[bits[2]] = bits[0]
        if kind=='remote': dresult[bits[0]] = bits[1]
    return dresult


def compare_sums(dlocal,dremote):
    '''Compare remote and local checksums if they're different re-download file '''
    for fname in sorted(dlocal.keys()):
        if fname not in dremote.keys():
            print('there is no remote cksum for file ', fname) 
        elif dlocal[fname] != dremote[fname]:
            print('problem with ' , fname)
            print( dlocal[fname], dremote[fname])
            fyr,fday = get_tstamp(fname)
            update_file(fyr,fday,fname)
        else:
            pass
    return


def update_file(fyr,fday,fname):
    ''' Delete file and download it from scratch '''
    global syr, http_url, data_dir
    local_file="/".join([data_dir,syr,fname])
    os.remove(local_file)
    print("/".join([http_url,fyr,fday,fname]))
    download_file("/".join([http_url,fyr,fday,fname]),local_file)
    return


def download_file(url,fname):
    ''' download file using requests '''
    global session
    r = session.get(url)
    with open(fname, 'wb') as f:
        f.write(r.content)
    del r
    return 


def download_dir():
    ''' download entire year directory '''
    global session, http_url, syr
    #print(http_url + "/" + syr)
    r = session.get(http_url + "/" + syr)
    soup = BeautifulSoup(r.content,'html.parser')
    for link in soup.find_all('a',string=re.compile('^\d{3}/')):
        subdir=link.get('href')
        #print(subdir)
        r2 = session.get("/".join([http_url,syr,subdir]))
        soup2 = BeautifulSoup(r2.content,'html.parser')
        for sub in soup2.find_all('a',string=re.compile('^3B42.*.HDF$')):
            href=sub.get('href')
            local_name="/".join([data_dir,syr,href])
            if not os.path.exists(local_name):
                print(local_name, 'new')
                download_file("/".join([http_url,syr,subdir,href]), local_name)
    print('Download for year '+ syr + ' is complete')
    return


def open_session():
    ''' open a requests session to manage connection to webserver '''
    session = requests.session()
    p = session.post("http://urs.earthdata.nasa.gov", {'user':username,'password':password})
    #cookies=requests.utils.dict_from_cookiejar(session.cookies)
    return session 


def main():
    global yr, syr, http_url, data_dir, session
    # check python version
    if sys.version_info < ( 2, 7):
        # python too old, kill the script
        sys.exit("This script requires Python 2.7 or newer!")
    # define http_url for TRMM http server and data_dir for local collection
    http_url='https://disc2.nascom.nasa.gov/data/s4pa/TRMM_L3/TRMM_3B42'
    data_dir='/g/data1/ua8/NASA_TRMM/TRMM_L3/TRMM_3B42/'
    run_dir='/g/data1/ua8/Download/NASA_TRMM/'
    # read year as external argument and move to data directory
    inputs=parse_input()
    yr=inputs["year"]
    syr=str(yr)
    current=inputs["current"]
    force=inputs["force"]
    try:
        os.chdir(data_dir + syr)
    except:
        os.mkdir(data_dir + syr)
    # open a request session and download cookies
    session = open_session()
    # if current flag is True, download/update the all year first:
    if current:
        download_dir()
    # create list of local HDF files for year
    hdf_list=sorted(os.listdir(data_dir + syr))

    # try to open the local checksum file for the year if it doesn't exist create one
    local_file = run_dir + '/trmm_local_cksum_' + syr + '.txt'
    if os.path.exists(local_file) and not force:
        flocal = open(local_file,'r')
        dlocal = read_sums(flocal,'local')
    else:
        print('Local checksum file for year ',syr, ' does not exist,\n calculating now')
        if force: os.remove(local_file)
        flocal = open(local_file,'w')
        dlocal = calculate_cksum(hdf_list, flocal)
    flocal.close()
    # get remote checksums from file if exists, or retrieve them using xml
    # and save to file
    remote_file=run_dir + '/trmm_remote_cksum_' + syr + '.txt'
    if os.path.exists(remote_file):
        fremote=open(remote_file,'r')
        dremote = read_sums(fremote,'remote')
    else:
        print('Remote checksum file for year ', syr, ' does not exist,\n retrieving now')
        fremote=open(remote_file,'w')
        dremote = retrieve_xml(hdf_list,fremote)
    fremote.close()
    # compare local and remote checksum
    compare_sums(dlocal,dremote)


if __name__ == "__main__":
    main()
