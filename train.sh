#!/bin/bash

GPU_ID=$1
DATASET="pascal_voc"
NET=$2

case ${NET} in
  vgg16)
    cp lib/nets/network_vgg16.py lib/nets/network.py
    bash experiments/scripts/train_faster_rcnn.sh $GPU_ID $DATASET $NET
    echo "Change network_vgg16"
    rm -rf lib/nets/network.py
    ;;
  res101)
    cp lib/nets/network_resnet.py lib/nets/network.py
    echo "Change network_resnet"
    bash experiments/scripts/train_faster_rcnn.sh $GPU_ID $DATASET $NET
    rm -rf lib/nets/network.py
    ;;
  *)
    echo "You should choose either vgg16 or res101"
    exit
    ;;
esac
