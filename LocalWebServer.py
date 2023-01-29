import RPi.GPIO as GPIO
import os
import json
import config
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

 #Method to get timestamp from WorldTime API
def getTimeFromAPI():
    timeResponse=requests.get(config.WORLDTIMEAPI_URL)
    if(timeResponse.status_code==200):
        timeData=timeResponse.json()
        dateTime=timeData['datetime']
        dateTime=dateTime.replace("T"," ")
        dateTime=dateTime.split(".",1)[0]+" "
        return dateTime
    else:
        return "**Time API Error**: "

class MyServer(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def _redirect(self, path):
        self.send_response(303)
        self.send_header('Content-type', 'text/html')
        self.send_header('Location', path)
        self.end_headers()

    def do_GET(self):
        if(self.path=='/allRelayOff'):
            i=0
            for i in range (8):
                requests.get(config.MANUAL_RELAY_CONTROL_OFF_URL.format(i))
            self.path = config.WEBPAGE_DIR+'allRelayOff.html'
            try:
                file = open(self.path[1:]).read()
                f=open(config.ESP32LOG_FILE_NAME,"r")
                self.do_HEAD()
                self.wfile.write(bytes(file,"utf-8"))
            except:
                self.send_response(404)
        if(self.path=='/fetchDeviceStatus'):
            pin_report=['','','','','','','','']
            f=open(config.ESP32LOG_FILE_NAME,"r")
            log_list = f.readlines()
            for line in reversed(log_list):
                if(line.find('DHT11')!=-1):
                    filteredDHTLogLatest = line
                    f.close()
                    break
            if 'error' in filteredDHTLogLatest:
                report = 'DHT11 sensor seems faulty or ESP32 is unable to receive data from it.'
            else:
                report = 'According to the log, DHT11 sensor appears to be functioning properly.'
            f=open(config.ESP32LOG_FILE_NAME,"r")
            log_list = f.readlines()
            for line in reversed(log_list):
                if(line.find('OpenWeather')!=-1):
                    filteredWeatherLogLatest = line
                    f.close()
                    break
            if 'error' in filteredWeatherLogLatest:
                report_weather = 'ESP32 is not able to get a valid response from OpenWeather API. Blynk may not have live weather data'
            else:
                report_weather = 'Log indicates ESP32 was able to establish connection with OpenWeather API and get a valid response'
            for i in range (0,8):
                f=open(config.ESP32LOG_FILE_NAME,"r")
                log_list = f.readlines()
                for line in reversed(log_list):
                    if(line.find('Switched Relay State for Virtual Pin {}'.format(i))!=-1):
                        pin_report[i] = line
                        f.close()
                        break
            self.path = config.WEBPAGE_DIR+'deviceStatus.html'
            try:
                file = open(self.path[1:]).read()
                self.do_HEAD()
                self.wfile.write(bytes(file.format(report,report_weather,pin_report[0][-4],pin_report[1][-4],pin_report[2][-4],pin_report[3][-4],pin_report[4][-4],pin_report[5][-4],pin_report[6][-4],pin_report[7][-4]),"utf-8"))
            except:
                self.send_response(404)
            
        if(self.path=='/sendEmailLog'):
            mail_content = '''Hello,

Please find attached the latest log file from admin server.

Thank You,
Pi
            '''
            message = MIMEMultipart()
            message['From'] = config.SENDER_ADDRESS
            message['To'] = config.RECEIVER_ADDRESS
            message['Subject'] = config.ESP32_LOG_EMAIL_SUBJECT
            message.attach(MIMEText(mail_content, 'plain'))
            attach_file_name = config.ESP32LOG_FILE_NAME
            attach_file = open(attach_file_name, 'rb')
            payload = MIMEBase('application', 'octate-stream')
            payload.set_payload((attach_file).read())
            encoders.encode_base64(payload)
            payload.add_header('Content-Decomposition', 'attachment', filename='%s' % 'ESP32.log')
            message.attach(payload)
            session = smtplib.SMTP(config.SMTP_GMAIL_SERVER, config.SMTP_PORT_NO)
            session.starttls()  
            session.login(config.SENDER_ADDRESS, config.SENDER_PASS)  
            text = message.as_string()
            session.sendmail(config.SENDER_ADDRESS, config.RECEIVER_ADDRESS, text)
            session.quit()
            self.path = config.WEBPAGE_DIR+'emailLog.html'
            try:
                file = open(self.path[1:]).read()
                self.do_HEAD()
                self.wfile.write(bytes(file.format(config.SENDER_ADDRESS,config.RECEIVER_ADDRESS,attach_file_name,getTimeFromAPI()),"utf-8"))
            except:
                self.send_response(404)
            
        if(self.path=='/blynk-connection'):
            content_length = int(self.headers['content-length'])
            body = self.rfile.read(content_length)
            result = json.loads(body)
            ping = result['ping_value']
            self.do_HEAD()
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"ESP32 connected to Blynk with ping:"+str(ping)+"\n")
            f.close()
        if(self.path=='/highTempEmailSuccess'):
            self.do_HEAD()
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"ESP32 has triggered a successful IFTT email event due to high temperature detection."+"\n")
            f.close()
        if(self.path=='/blynkDisconnect'):
            self.do_HEAD()
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"Critical: ESP32 has disconnected from blynk. Please check on priority"+"\n")
            f.close()
        if(self.path=='/highTempEmailFail'):
            content_length = int(self.headers['content-length'])
            body = self.rfile.read(content_length)
            result = json.loads(body)
            error = result['error']
            self.do_HEAD()
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"ESP32 has attempted to trigger an IFTT mail event but event has failed with status code: {} Due to this email has not been send".format(error)+"\n")
            f.close()
        if(self.path=='/updateWeatherFail'):
            content_length = int(self.headers['content-length'])
            body = self.rfile.read(content_length)
            result = json.loads(body)
            status_code = result['code']
            self.do_HEAD()
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"ESP32 received error response code {} when trying to connect with OpenWeatherAPI. Blynk may not have the latest weather data due to this.".format(status_code)+"\n")
            f.close()
        if(self.path=='/updateDHTSuccess'):
            content_length = int(self.headers['content-length'])
            body = self.rfile.read(content_length)
            result = json.loads(body)
            temp = result['temp']
            hum = result['hum']
            self.do_HEAD()
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"ESP32 received sensor readings from DHT11 and updated the sensor data to Blynk. (Temperature: {} Humidity: {})".format(temp,hum)+"\n")
            f.close()
        if(self.path=='/updateDHTFail'):
            content_length = int(self.headers['content-length'])
            body = self.rfile.read(content_length)
            result = json.loads(body)
            error = result['error']
            self.do_HEAD()
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"ESP32 could not read DHT11 sensor. Sensor returned error: {} Please check connection or if the sensor is faulty".format(error)+"\n")
            f.close()
        if (self.path=="/updateWeatherSuccess"):
            content_length = int(self.headers['content-length'])
            body = self.rfile.read(content_length)
            result = json.loads(body)
            temp = result['temp']
            hum = result['hum']
            report = result['report']
            pressure = result['pressure']
            f=open(config.ESP32LOG_FILE_NAME,"a")
            f.write(getTimeFromAPI()+"ESP32 received weather data from OpenWeather API and send data to Blynk cloud (Temperature = {} Humidity = {} Report = {} Pressure = {})".format(temp,hum,report,pressure)+"\n")
            f.close()
        if (self.path=='/getLatestDHT'):
            f=open(config.ESP32LOG_FILE_NAME,"r")
            log_list = f.readlines()
            for line in reversed(log_list):
                if(line.find('DHT11')!=-1):
                    filteredDHTLogLatest = line
                    f.close()
                    break
            if 'error' in filteredDHTLogLatest:
                report = 'DHT11 sensor seems faulty or ESP32 is unable to receive data from it.'
            else:
                report = 'According to the log, DHT11 sensor appears to be functioning properly.'
                
            self.path = config.WEBPAGE_DIR+'latestDHTLog.html'
            try:
                file = open(self.path[1:]).read()
                self.do_HEAD()
                self.wfile.write(bytes(file.format(filteredDHTLogLatest,report),"utf-8"))
            except:
                self.send_response(404)
                
        if (self.path=='/getLatestWeather'):
            f=open(config.ESP32LOG_FILE_NAME,"r")
            log_list = f.readlines()
            for line in reversed(log_list):
                if(line.find('OpenWeather')!=-1):
                    filteredWeatherLogLatest = line
                    f.close()
                    break
            if 'error' in filteredWeatherLogLatest:
                report = 'ESP32 is not able to get a valid response from OpenWeather API. Blynk may not have live weather data'
            else:
                report = 'Log indicates ESP32 was able to establish connection with OpenWeather API and get a valid response'
                
            self.path = config.WEBPAGE_DIR+'latestWeatherLog.html'
            try:
                file = open(self.path[1:]).read()
                self.do_HEAD()
                self.wfile.write(bytes(file.format(filteredWeatherLogLatest,report),"utf-8"))
            except:
                self.send_response(404)

        if (self.path=='/getLog'):
            f=open(config.ESP32LOG_FILE_NAME,"r")
            records = f.readlines()[-10:]
            record1 = records[0]
            record2 = records[1]
            record3 = records[2]
            record4 = records[3]
            record5 = records[4]
            record6 = records[5]
            record7 = records[6]
            record8 = records[7]
            record9 = records[8]
            record10 = records[9]
            f.close()
            self.path = config.WEBPAGE_DIR+'logs.html'
            try:
                file = open(self.path[1:]).read()
                self.do_HEAD()
                self.wfile.write(bytes(file.format(record1,record2,record3,record4,record5,record6,record7,record8,record9,record10),"utf-8"))
            except:
                self.send_response(404)
            
        if (self.path=='/updateRelayStatus'):
            content_length = int(self.headers['content-length'])
            body = self.rfile.read(content_length)
            result = json.loads(body)
            pin = result['pin']
            value = result['value']
            f=open(config.ESP32LOG_FILE_NAME,"a")
            if (pin == '0'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,12,value)+"\n")
            if (pin == '1'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,13,value)+"\n")
            if (pin == '2'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,14,value)+"\n")
            if (pin == '3'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,15,value)+"\n")
            if (pin == '4'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,21,value)+"\n")
            if (pin == '5'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,23,value)+"\n")
            if (pin == '6'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,25,value)+"\n")
            if (pin == '7'):
                f.write(getTimeFromAPI()+config.RELAYSTATEMSG.format(pin,26,value)+"\n")
            f.close()
            self.do_HEAD()
            
        elif(self.path == '/'):
            self.path = config.WEBPAGE_DIR+'index.html'
            try:
                file = open(self.path[1:]).read()
                self.do_HEAD()
                self.wfile.write(bytes(file.format(config.WEB_SERVER_VERSION,config.HOST_NAME,config.HOST_PORT),"utf-8"))
            except:
                self.send_response(404)

    def do_POST(self):
        print('here');


# # # # # Main # # # # #

if __name__ == '__main__':
    http_server = HTTPServer((config.HOST_NAME, config.HOST_PORT), MyServer)
    print("PI Local Web Server Starts - %s:%s" % (config.HOST_NAME, config.HOST_PORT))
    print('Developed by Jacob')

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.server_close()
