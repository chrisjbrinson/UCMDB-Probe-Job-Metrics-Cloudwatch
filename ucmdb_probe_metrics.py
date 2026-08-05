import urllib.request
import urllib.parse
import http.cookiejar
import ssl
import re
from bs4 import BeautifulSoup
import boto3
import socket
import json

ssl._create_default_https_context = ssl._create_unverified_context

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

client = boto3.client("secretsmanager", region_name="us-east-1")

response = client.get_secret_value(
	SecretId="<SECRET_NAME>"
)

secret = json.loads(response["SecretString"])

USERNAME=
PASSWORD = 


PROBE = "localhost"

LOGIN_URL = f"https://{PROBE}:8453/jmx-console/"
JMX_URL = LOGIN_URL + "HtmlAdaptor"


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------

def jmx_login():

    cookiejar = http.cookiejar.CookieJar()

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookiejar)
    )

    urllib.request.install_opener(opener)

    # Create session
    urllib.request.urlopen(JMX_URL)

    # Login
    login_data = urllib.parse.urlencode({
        "j_username": USERNAME,
        "j_password": PASSWORD,
        "submit": "Login"
    }).encode("utf-8")

    urllib.request.urlopen(
        urllib.request.Request(
            LOGIN_URL + "j_security_check",
            data=login_data,
            method="POST"
        )
    )

    return cookiejar


# ------------------------------------------------------------------
# Retrieve CSRF Token
# ------------------------------------------------------------------

def get_token(cookiejar):

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookiejar)
    )

    urllib.request.install_opener(opener)

    params = urllib.parse.urlencode({
        "action": "inspectMBean",
        "name": "Local_:type=JobsInformation"
    })

    html = urllib.request.urlopen(
        JMX_URL + "?" + params
    ).read().decode("utf-8")

    match = re.search(
        r'name="ucmdbToken"\s+value="([^"]+)"',
        html
    )

    if not match:
        raise Exception("Unable to retrieve ucmdbToken")

    return match.group(1)


# ------------------------------------------------------------------
# Invoke viewJobsStatuses
# ------------------------------------------------------------------

def view_jobs(token, cookiejar):

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookiejar)
    )
    urllib.request.install_opener(opener)

    post_data = urllib.parse.urlencode({
        "action": "invokeOpByName",
        "name": "Local_:type=JobsInformation",
        "methodName": "viewJobsStatuses",
        "arg0": "True",
        "arg1": "True",
        "ucmdbToken": token
    }).encode("utf-8")
    
    response = urllib.request.urlopen(
        urllib.request.Request(
            JMX_URL,
            data=post_data,
            method="POST"
        )
    )
    html = response.read().decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    print(f"Found {len(tables)} tables")

    if len(tables) < 2:
        raise Exception("Couldn't find the jobs table.")

    jobs = []

    for row in tables[1].find_all("tr")[1:]:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]

        if cols:
            #jobs.append(cols)
            jobs.append({
                "id": cols[0],
                "name": cols[1],
                "status": cols[2],
                "triggered_cis": cols[3],
                "errors": cols[4],
                "last_run": cols[5],
                "next_run": cols[6],
                "duration": cols[7],
                "average_duration": cols[8],
                "recurrence": cols[9]
            })
    
    return jobs

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------



def sanitize_metric_name(name):
    return re.sub(r'[^A-Za-z0-9]', '_', name)

def main():

    print("Logging in...")
    cookies = jmx_login()

    print("Retrieving token...")
    token = get_token(cookies)

    print("Calling viewJobsStatuses...")
    jobs = view_jobs(token, cookies)

    probe = socket.gethostname()

    cw = boto3.client("cloudwatch", region_name="us-east-1")

    namespace = f"UCMDB/{probe}"

    for job in jobs:

        print(f"Publishing metrics for {job['name']}")

        metric_prefix = sanitize_metric_name(job["name"])

        cw.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": f"{metric_prefix}.Errors",
                    "Value": float(job["errors"]),
                    "StorageResolution": 60
                },
                {
                    "MetricName": f"{metric_prefix}.TriggeredCIs",
                    "Value": float(job["triggered_cis"]),
                    "StorageResolution": 60
                },
                {
                    "MetricName": f"{metric_prefix}.Duration",
                    "Value": float(job["duration"].replace(",", "")),
                    "StorageResolution": 60
                },
                {
                    "MetricName": f"{metric_prefix}.AverageDuration",
                    "Value": float(job["average_duration"].replace(",", "")),
                    "StorageResolution": 60
                }
            ]
        )

    print("Done")


if __name__ == "__main__":
    main()

          
      
