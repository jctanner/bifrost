#!/bin/bash

checkip () {
    RIP=$(dig $1 | fgrep -A1 "ANSWER SECTION" | egrep -v "ANSWER" | awk '{print $NF}')
    echo $RIP
}


NODES=$(sudo virsh list --all --name)
for NODE in $NODES; do
    MAC=$(sudo virsh domiflist $NODE | egrep ^vnet | awk '{print $NF}')
    IPADDR=$(arp -e | fgrep $MAC)
    RIPADDR=$(checkip $IPADDR)
    echo "$NODE mac_address=$MAC ansible_ssh_host=$RIPADDR ansible_ssh_user=centos"
done
