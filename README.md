# UCMDB Probe Job Metrics to Cloudwatch

A simple python script that uses the viewJobsStatuses JMX method on a Windows UCMDB Probe to retrieve metrics related to the probe's jobs. These metrics are then uploaded to Cloudwatch.
Also included is an ansible playbook to push the script to your probes and create a scheduled task via Task Scheduler.

# Note
- This was created around UCMDB version 25.4
- It is assumed the probe server(s) is assigned an AWS instance role with permissions to access Secrets Manager, and write to Cloudwatch.