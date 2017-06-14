#!/usr/bin/env python

import json
import subprocess
import sys
import time
from pprint import pprint

NODECOUNT = 6
#NODECOUNT = 4


def run_command(cmd, wait=True):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if wait:
        (so, se) = p.communicate()
        return (p.returncode, so, se)
    else:
        return (None, None, None)


def get_nodes():
    cmd = 'ironic --json node-list'
    (rc, so, se) = run_command(cmd)
    try:
        nodes = json.loads(so)
    except:
        nodes = []
    return nodes


def get_ports():
    cmd = 'ironic --json port-list'
    (rc, so, se) = run_command(cmd)
    try:
        nodes = json.loads(so)
    except:
        nodes = []
    return nodes


def get_node_ports(uuid):
    cmd = 'ironic --json node-port-list %s' % uuid
    #print(cmd)
    (rc, so, se) = run_command(cmd)
    #print(so)
    #print(se)
    ports = json.loads(so)
    return ports


def get_domains():
    cmd = 'sudo virsh list --all --name'
    (rc, so, se) = run_command(cmd)
    domains = so.split('\n')
    domains = [x.strip() for x in domains if x.strip()]
    return domains


def get_domain_info(name):
    info = {}
    cmd = 'sudo virsh dominfo %s' % name
    (rc, so, se) = run_command(cmd)
    lines = so.split('\n')
    for line in lines:
        parts = line.split(':', 1)
        parts = [x.strip() for x in parts if x.strip()]
        if parts:
            info[parts[0]] = parts[1]
    return info


def boot_domain(name):
    cmd = 'sudo virsh start %s' % name
    (rc, so, se) = run_command(cmd)


def get_domain_mac(name):
    cmd = 'sudo virsh dumpxml %s | fgrep "mac address"' % name
    (rc, so, se) = run_command(cmd)
    parts = so.split("'")
    mac = parts[1]
    return mac


def get_vbmc_node_info(name):
    data = {}
    cmd = 'sudo vbmc show %s' % name
    (rc, so, se) = run_command(cmd)
    lines = so.split('\n')
    for line in lines:
        if 'Property' in line or line.startswith('+'):
            continue
        parts = line.split('|')
        parts = [x.strip() for x in parts if x.strip()]
        if parts:
            if parts[1].isdigit():
                parts[1] = int(parts[1])
            data[parts[0]] = parts[1]
    return data


def create_vbmc_node(name):
    baseport = 623
    nodenum = name.replace('openshift', '')
    nodenum = int(nodenum)
    port = baseport + nodenum
    cmd = 'sudo vbmc add %s --username=admin --password=redhat --port=%s' % (name, port)
    (rc, so, se) = run_command(cmd, wait=False)

    cmd = 'sudo vbmc start %s' % name
    (rc, so, se) = run_command(cmd, wait=False)


def update_ironic_node_info(uuid, domain, ipmi_host='127.0.0.1', ipmi_port=623, ipmi_username='admin', ipmi_password='redhat'):
    cmd = 'ironic node-update %s add' % uuid
    cmd += ' name=%s' % domain
    cmd += ' driver_info/ipmi_username=%s' % ipmi_username
    cmd += ' driver_info/ipmi_password=%s' % ipmi_password
    cmd += ' driver_info/ipmi_address=%s' % ipmi_host
    cmd += ' driver_info/ipmi_port=%s' % ipmi_port

    # workaround
    cmd += ' instance_info/root_gb=10'

    # boot info
    #cmd += ' instance_info/ramdisk=http://192.168.122.1:8080/ipa.initramfs'
    #cmd += ' instance_info/kernel=http://192.168.122.1:8080/ipa.vmlinuz'
    cmd += ' instance_info/image_source=http://192.168.122.1:8080/CentOS-Atomic-Host-7-GenericCloud.qcow2'
    cmd += ' instance_info/image_checksum=a2aaaefa1652ee2f6d081ae600461d2b'

    # used for pxe+writing the image
    cmd += ' driver_info/deploy_ramdisk=http://192.168.122.1:8080/ipa.initramfs'
    cmd += ' driver_info/deploy_kernel=http://192.168.122.1:8080/ipa.vmlinuz'

    (rc, so, se) = run_command(cmd)
    print(str(rc),se)


def build(nodecount=NODECOUNT):

    print('#####################################')
    print('# Checking domains')
    print('#####################################')
    domains = get_domains()
    if not domains or len(domains) != nodecount:
        print('#####################################')
        print('# Creating domains')
        print('#####################################')
        #cmd = 'sudo OUTFILE=/tmp/nodes.csv NODEBASE=openshift NODECOUNT=3 ./create_vm_nodes.sh'
        cmd = 'sudo OUTFILE=/tmp/nodes.csv NODEBASE=openshift NODECOUNT=%s ./create_vm_nodes.sh' % nodecount
        (rc, so, se) = run_command(cmd)
        if rc != 0:
            print(so)
            print(se)
            sys.exit(rc)
        domains = get_domains()
    print(domains)

    print('#####################################')
    print('# Starting domains')
    print('#####################################')
    for domain in domains:
        dinfo = get_domain_info(domain)
        if dinfo['State'] == 'shut off':
            print('starting domain %s' % domain)
            boot_domain(domain)

    print('#####################################')
    print('# Wait for ironic node registrations')
    print('#####################################')
    # Wait for nodes to register with ironic
    while len(get_nodes()) < nodecount:
        print('# waiting for nodes to boot: sleep 10s')
        pprint(get_nodes())
        time.sleep(10)

    print('#####################################')
    print('# Fetch node info')
    print('#####################################')
    nodes = get_nodes()
    pprint(nodes)

    print('#####################################')
    print('# Fetch port info')
    print('#####################################')
    ports = get_ports()
    pprint(ports)

    print('#####################################')
    print('# Processing nodes/domains')
    print('#####################################')
    for domain in domains:
        print('# domain: %s' % domain)
        mac = get_domain_mac(domain)
        node_uuid = None
        port = None

        print('# vbmc info %s' % domain)
        vbmc_info = get_vbmc_node_info(domain)
        if not vbmc_info:
            print('# vbmc create %s' % domain)
            create_vbmc_node(domain)
            while not get_vbmc_node_info(domain):
                print('# waiting for vbmc on %s' % domain)
                time.sleep(5)
        vbmc_info = get_vbmc_node_info(domain)
        pprint(vbmc_info)

        print('# port list %s' % domain)
        for node in nodes:
            nports = get_node_ports(node['uuid'])
            for nport in nports:
                if nport['address'] == mac:
                    node_uuid = node['uuid']
                    #port = nport
                    break

        print('#####################################')
        print('# Update %s node info' % domain)
        print('#####################################')
        update_ironic_node_info(node_uuid, domain, ipmi_port=vbmc_info['port'])
        print(domain,mac,node_uuid)


def main():

    for x in range(1, NODECOUNT+1):
        print(x)
        build(nodecount=x)

if __name__ == "__main__":
    main()
