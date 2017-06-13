#!/usr/bin/env python

import json
import subprocess
import sys


def run_command(cmd):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (so, se) = p.communicate()
    return (p.returncode, so, se)


def get_nodes():
    cmd = 'ironic --json node-list'
    (rc, so, se) = run_command(cmd)
    nodes = json.loads(so)
    return nodes

    
def get_ports():
    cmd = 'ironic --json port-list'
    (rc, so, se) = run_command(cmd)
    nodes = json.loads(so)
    return nodes


def get_node_ports(uuid):
    cmd = 'ironic --json node-port-list %s' % uuid
    #print(cmd)
    (rc, so, se) = run_command(cmd)
    #print(so)
    #print(se)
    try:
        ports = json.loads(so)
    except:
        print(str(so) + str(se))
        ports = []
    return ports


def get_domains():
    cmd = 'sudo virsh list --all --name'
    (rc, so, se) = run_command(cmd)
    domains = so.split('\n')
    domains = [x.strip() for x in domains if x.strip()]
    return domains


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


def update_ironic_node_info(uuid, domain, ipmi_host='127.0.0.1', ipmi_port=623, ipmi_username='admin', ipmi_password='redhat'):
    cmd = 'ironic node-update %s add' % uuid
    cmd += ' name=%s' % domain
    cmd += ' driver_info/ipmi_username=%s' % ipmi_username
    cmd += ' driver_info/ipmi_password=%s' % ipmi_password
    cmd += ' driver_info/ipmi_address=%s' % ipmi_host
    cmd += ' driver_info/ipmi_port=%s' % ipmi_port
    cmd += ' instance_info/ramdisk=http://192.168.122.1:8080/ipa.initramfs'
    cmd += ' instance_info/kernel=http://192.168.122.1:8080/ipa.vmkernel'

    cmd += ' instance_info/image_source=http://192.168.122.1:8080/CentOS-Atomic-Host-7-GenericCloud.qcow2'
    cmd += ' instance_info/image_checksum=a2aaaefa1652ee2f6d081ae600461d2b'

    # used for pxe+writing the image
    cmd += ' driver_info/deploy_ramdisk=http://192.168.122.1:8080/ipa.initramfs'
    cmd += ' driver_info/deploy_kernel=http://192.168.122.1:8080/ipa.vmkernel'

    (rc, so, se) = run_command(cmd)
    print(str(rc),se)


def clear_node(domain, uuid):
    # 1. set maintenance mode
    cmd = 'ironic node-set-maintenance %s on' % uuid
    (rc, so, se) = run_command(cmd)

    # 2. delete node
    cmd = 'ironic node-delete %s' % uuid
    (rc, so, se) = run_command(cmd)
    if rc != 0:
        print('rc: %s' % rc)
        print('so: %s' % rc)
        print('se: %s' % rc)

    # 3. stop vbmc
    cmd = 'sudo vbmc stop %s' % domain
    (rc, so, se) = run_command(cmd)

    # 4. delete vbmc
    cmd = 'sudo vbmc delete %s' % domain
    (rc, so, se) = run_command(cmd)

    # 5. stop domain
    cmd = 'sudo virsh destroy %s' % domain
    (rc, so, se) = run_command(cmd)

    # 6. delete domain
    cmd = 'sudo virsh undefine %s' % domain
    (rc, so, se) = run_command(cmd)

 
def main():
    domains = get_domains()
    print(domains)
    nodes = get_nodes()
    print(nodes)
    ports = get_ports()
    print(ports)

    for domain in domains:
        mac = get_domain_mac(domain)
        node = None
        node_uuid = None
        port = None

        vbmc_info = get_vbmc_node_info(domain)

        for node in nodes:
            nports = get_node_ports(node['uuid'])
            for nport in nports:
                if nport['address'] == mac:
                    node_uuid = node['uuid']
                    port = nport
                    break

        #update_ironic_node_info(node_uuid, domain, ipmi_port=vbmc_info['port'])
        clear_node(domain, node_uuid)
        print(domain,mac,node_uuid)

    for node in nodes:
        clear_node(None, node['uuid'])


if __name__ == "__main__":
    main()
