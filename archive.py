#!/usr/bin/env python
import sys
import os
import json
import codecs
import time
import dateutil.parser
import math
import cpapi
import cputils
import logbook

# log_file = open('log_monitoring', 'w')

logger = logbook.Logger('archive')
log = logbook.FileHandler('monitoring.log')
log.push_application()
start_time = time.time()

class CmdLine:
    def __init__(self):
        self.authFilename = "archive.auth"
        self.starting = None
        self.ending = None
        self.reportModule = None
        self.url_base = "https://api.cloudpassage.com"


    def processArgs(self, argv):
        allOK = True
        self.progdir = os.path.dirname(sys.argv[0])
        for arg in argv[1:]:
            if (arg.startswith("--auth=")):
                self.authFilename = arg.split("=")[1]
            elif (arg.startswith("--base=")):
                self.base = arg.split("=")[1]
            elif (arg == "-h") or (arg == "-?"):
                allOK = False
            else:
                print >>sys.stderr, "Unknown argument: %s" % arg
                allOK = False
        return allOK

    def usage(self, progname):
        print >> sys.stderr, "Usage: %s [flag] [...]" % os.path.basename(progname)
        print >> sys.stderr, "Where flag is one or more of the following options:"
        print >> sys.stderr, "--auth=<filename>\tSpecify name of file containing API credentials"
        print >> sys.stderr, "--base=<url>\t\tSpecify the URL of the Halo REST API"


class ArchiveData:
    def __init__(self):
        self.api = cpapi.CPAPI()
        self.directory = os.getcwd()

    def listServer(self):
        print "Start archiving issues."
        logger.info("start archiving issues.")
        count = 1
        server_List = []
        Finish = False
        url = "%s:%d/v1/servers?per_page=100&page=1" %(self.api.base_url, self.api.port)
        (data, authError,error_msg) = self.api.doGetRequest(url, self.api.authToken)
        if data != None:
            logger.info("First API was successful! Data is good.")
        while (data == None) and (count < 4):
            logger.warn("Failed to connect to %s" % url)
            resp = self.api.authenticateClient()
            (data, authError, error_msg) = self.api.doGetRequest(url, self.api.authToken)
            logger.warn(error_msg)
            logger.warn("retry: %d time" % count + "on %d" % url) 
            if (data != None):
                logger.info("Successfully retreive server list from %d" % url)
            count += 1
        while(data != None) and (Finish == False):
            if ('servers' in data):
                listServers = json.loads(data)
                serverList = listServers['servers']
                for server in serverList:
                    server_List.append((server['id'], server))
                if ('pagination' in listServers):
                    if ('next' in listServers['pagination']):
                        url = listServers['pagination']['next']
                        countPagination = 1
                        (data, authError, error_msg) = self.api.doGetRequest(url, self.api.authToken)
                        while (data == None) and (countPagination < 4):
                            resp = self.api.authenticateClient()
                            logger.warn(error_msg)
                            logger.warn("retry: %d time" % countPagination + "on %s" % url)
                            (data, authError, error_msg) = self.api.doGetRequest(url,self.api.authToken)
                            if (data != None):
                                logger.info("Successfully retreive server list from %s" % url)
                            countPagination +=1
                        if (count == 4):
                            logger.warn("Failed to connect to", url)
                    else: 
                        Finish = True
        return server_List


    def getServer_csm(self, serverList):
        for serverID, serverDetail in serverList:
            count = 1
            url = "%s:%d/v1/servers/%s/sca" % (self.api.base_url, self.api.port, serverID)
            (data, authError, error_msg) = self.api.doGetRequest(url, self.api.authToken)
            while (data == None) and (count < 4):
                resp = self.api.authenticateClient()
                logger.warn(error_msg)
                logger.warn("retry: %d time" % count + "on %s" % url)
                (data, authError, error_msg) = self.api.doGetRequest(url, self.api.authToken)
                if (data != None):
                    logger.info("Successfully retreive server issue from %s" % url)    
                count += 1
            if (data != None):
                serverIssue = json.loads(data)
                server_hostname = serverIssue['hostname']
                if ('scan' in serverIssue):
                    scanDetail = serverIssue['scan']
                    scan_time = dateutil.parser.parse(scanDetail['created_at'])
                    scan_id = scanDetail['id']
                    if ('findings' in scanDetail):
                        if (len(scanDetail['findings']) != 0):
                            sca_data = serverIssue
                            filename = (self.directory + "/output/" + str(scan_time.year) + "/" + str(scan_time.month) + "/" + str(scan_time.day) +
                                         "/" + server_hostname + "/" + "csm" + "--" + scan_id + ".json")
                            if not os.path.exists(os.path.dirname(filename)):
                                os.makedirs(os.path.dirname(filename))
                            with open(filename, "w") as f:
                                json.dump(sca_data, f)
                                logger.info("Successfully archive csm scan from: %s" % url)
            else:
                logger.warn("Failed to connect to %s" % url)

            if (serverDetail != None):               
                fileServer = (self.directory + "/output/" + str(scan_time.year) + "/" + str(scan_time.month) + "/" + str(scan_time.day) +
                             "/" + server_hostname + "/" + "serverInfo" + ".json")
                if not os.path.exists(os.path.dirname(fileServer)):
                    os.makedirs(os.path.dirname(fileServer))
                with open(fileServer, "w") as f:
                    json.dump(serverDetail, f)
                    logger.info("Successfully download the server information: %s" % url)

    def getServer_sva(self, serverList):
        for serverID, serverDetail in serverList:
            count = 1
            url = "%s:%d/v1/servers/%s/svm" % (self.api.base_url, self.api.port, serverID)
            (data, authError, error_msg) = self.api.doGetRequest(url, self.api.authToken)
            while (data == None) and (count < 4):
                resp = self.api.authenticateClient()
                logger.warn(error_msg)
                logger.warn("retry: %d time" % count + "on %s" % url)
                (data, authError, error_msg) = self.api.doGetRequest(url, self.api.authToken)
                if (data != None):
                    logger.info("Successfully retreive server issue from %s" % url)    
                count += 1
            if (data != None):
                serverIssue = json.loads(data)
                server_hostname = serverIssue['hostname']
                if ('scan' in serverIssue):
                    scanDetail = serverIssue['scan']
                    scan_time = dateutil.parser.parse(scanDetail['created_at'])
                    scan_id = scanDetail['id']
                    if ('findings' in scanDetail):
                        if (len(scanDetail['findings']) != 0):
                            svm_data = serverIssue
                            filename = (self.directory + "/output/" + str(scan_time.year) + "/" + str(scan_time.month) + "/" + str(scan_time.day) +
                                         "/" + server_hostname + "/" + "sva" + "--" + scan_id + ".json")
                            if not os.path.exists(os.path.dirname(filename)):
                                os.makedirs(os.path.dirname(filename))
                            with open(filename, "w") as f:
                                json.dump(svm_data, f)
                            fileServer = (self.directory + "/output/" + str(scan_time.year) + "/" + str(scan_time.month) + "/" + str(scan_time.day) +
                                         "/" + server_hostname + "/" + "serverInfo" + ".json")
                            if not os.path.exists(os.path.dirname(fileServer)):
                                os.makedirs(os.path.dirname(fileServer))
                            with open(fileServer, "w") as f:
                                json.dump(serverDetail, f)
                                logger.info("Successfully archive csm scan from: %s" % url)

            else:
                logger.warn("Failed to connect to %s" %url)

            if (serverDetail != None):               
                fileServer = (self.directory + "/output/" + str(scan_time.year) + "/" + str(scan_time.month) + "/" + str(scan_time.day) +
                             "/" + server_hostname + "/" + "serverInfo" + ".json")
                if not os.path.exists(os.path.dirname(fileServer)):
                    os.makedirs(os.path.dirname(fileServer))
                with open(fileServer, "w") as f:
                    json.dump(serverDetail, f)
                    logger.info("Successfully download the server information: %s" % url)

    def mp (serverList):
        queue = multiprocessing.Queue()
        res = [multiprocessing.Process(target=self.getServer_csm, args=(queue, i)) for i in serverList]
        for p in res:
            p.start()
        for p in res:
            p.join()

    def run (self, cmd):
        (credentialList, errMsg) = cputils.processAuthFile(cmd.authFilename, cmd.progdir)
        if (errMsg != None):
            print >> sys.stderr, errMsg
            return False
        if len(credentialList) < 1:
            return False
        # print credentials
        credentials = credentialList[0]
        self.api.base_url = cmd.url_base
        self.api.key_id = credentials['id']
        self.api.secret = credentials['secret']
        resp = self.api.authenticateClient()
        if (not resp):
            return False
        serverList = self.listServer()
        print "--- %s servers ---" % (len(serverList))
        logger.info("--- %s servers ---" % (len(serverList)))  
        print "Start archiving configuration scan result"
        self.getServer_csm(serverList)
        print "Start archiving software vulnerablility scan result"
        self.getServer_sva(serverList)



if __name__ == "__main__":
    cmd = CmdLine()
    if not cmd.processArgs(sys.argv):
        cmd.usage(sys.argv[0])
    else:
        rep = ArchiveData()
        rep.run(cmd)
        print ("--- %s seconds ---" % (time.time() - start_time))
        logger.info("--- %s seconds ---" % (time.time() - start_time))

