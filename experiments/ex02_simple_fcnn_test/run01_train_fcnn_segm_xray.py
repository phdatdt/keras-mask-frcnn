#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'ar'

import time
import shutil
import os
import math
import matplotlib.pyplot as plt
import skimage.io as skio
import skimage.transform as sktf
import skimage.exposure as skexp
import numpy as np
import keras
from keras.layers import Conv2D, UpSampling2D, \
    Flatten, Activation, Reshape, MaxPooling2D, Input, merge
from keras.models import Model
import keras.losses
import keras.callbacks as kall
import pandas as pd

from keras.preprocessing.image import ImageDataGenerator
from keras.utils.vis_utils import plot_model as kplot
from keras.utils import np_utils
from keras.utils.vis_utils import plot_model

#####################################################
def buildModelFCNN_UpSampling2D(inpShape=(256, 256, 3),
                                numCls=2,
                                kernelSize=3,
                                numFlt = 8,
                                isUNetStyle=True,
                                unetStartLayer=1,
                                ppad='same',
                                numSubsampling=4,
                                numConvRep=2,
                                isDebug=False):
    dataInput = Input(shape=inpShape)
    ksiz = (kernelSize, kernelSize)
    psiz = (2, 2)
    x = dataInput
    # -------- Encoder --------
    lstMaxPools = []
    for cc in range(numSubsampling):
        for ii in range(numConvRep):
            x = Conv2D(filters= numFlt * (2**cc), kernel_size=ksiz, padding=ppad, activation='relu')(x)
        lstMaxPools.append(x)
        x = MaxPooling2D(pool_size=psiz)(x)
    # -------- Decoder --------
    for cc in range(numSubsampling):
        for ii in range(numConvRep):
            x = Conv2D(filters= numFlt * ( 2**(numSubsampling-cc-1) ), kernel_size=ksiz, padding=ppad, activation='relu')(x)
        x = UpSampling2D(size=psiz)(x)
        if isUNetStyle:
            if cc < (numSubsampling - unetStartLayer):
                x = keras.layers.concatenate([x, lstMaxPools[-1 - cc]], axis=-1)
    # 1x1 Convolution: emulation of Dense layer
    if numCls>2:
        x = Conv2D(filters=numCls, kernel_size=(1, 1), padding='valid', activation='linear')(x)
        x = Reshape([-1, numCls])(x)
        x = Activation('softmax')(x)
    else:
        x = Conv2D(filters=1, kernel_size=(1, 1), padding='valid', activation='sigmoid')(x)
        x = Flatten()(x)
    retModel = Model(dataInput, x)
    if isDebug:
        import matplotlib.pyplot as plt
        retModel.summary()
        fimg_model = 'tmp_model_buildModelFCNN_UpSampling2D.png'
        kplot(retModel, fimg_model, show_shapes=True)
        plt.imshow(skio.imread(fimg_model))
        plt.show()
    return retModel

#####################################################
if __name__ == '__main__':
    fidx = '../../data/idx-xray_test_dataset.txt'
    if not os.path.isfile(fidx):
        raise Exception('Cant find dataset file [{0}]'.format(fidx))
    #
    wdir=os.path.dirname(fidx)
    idxData=pd.read_csv(fidx)
    pathImg = idxData['path_img'].as_matrix()
    pathImg = [os.path.join(wdir,xx) for xx in pathImg]
    numImg = len(pathImg)
    #
    # (1) load data
    dataImg = None
    dataMsk = None
    dataY = None
    print (':: Loading image data into memory...')
    for ipathImg, pathImg in enumerate(pathImg):
        pathMsk = '{0}.bmp'.format(os.path.splitext(pathImg)[0])
        timg = np.expand_dims(skio.imread(pathImg).astype(np.float32), axis=-1) / 127.5 - 1.0
        tmsk = (skio.imread(pathMsk).astype(np.float32)>0).astype(np.float32)
        if dataImg is None:
            dataImg = np.zeros([numImg] + list(timg.shape), dtype=np.float32)
            dataMsk = np.zeros([numImg] + list(tmsk.shape), dtype=np.float32)
            dataY   = np.zeros([numImg] + [np.prod(tmsk.shape)], dtype=np.float32)
        dataImg[ipathImg] = timg
        dataMsk[ipathImg] = tmsk
        dataY  [ipathImg] = tmsk.reshape(-1)
        if (ipathImg%50)==0:
            print ('\t[{0}/{1}]'.format(ipathImg, numImg))
    print ('... [done]')
    # (2) split data train/validation
    ptrn=0.8
    ptrnNum = int(ptrn * numImg)
    rndIdx = np.random.permutation(range(numImg))
    rndIdxTrn = rndIdx[:ptrnNum]
    rndIdxVal = rndIdx[ptrnNum:]
    # (2.1) train
    trnX = dataImg[rndIdxTrn]
    trnM = dataMsk[rndIdxTrn]
    trnY = dataY[rndIdxTrn]
    # (2.2) validation
    valX = dataImg[rndIdxVal]
    valM = dataMsk[rndIdxVal]
    valY = dataY[rndIdxVal]
    #
    # (3) build model
    numEpochs = 100
    batchSize = 32
    pathModel_BestLoss = '{0}_model_best_loss.h5'.format(fidx)
    pathLog = '{0}_log.txt'.format(fidx)
    pathLogsTF = '{0}_logs'.format(fidx)
    inpShape = trnX.shape[1:]
    model = buildModelFCNN_UpSampling2D(inpShape=inpShape, isDebug=False)
    model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    model.summary()
    print ('-')
    # (4) train model
    model.fit(trnX, trnY,
        batch_size=batchSize,
        epochs=numEpochs,
        validation_data=(valX, valY),
        callbacks=[
            kall.ModelCheckpoint(pathModel_BestLoss, verbose=True, save_best_only=True, monitor='val_loss'),
            kall.CSVLogger(pathLog, append=True),
            kall.TensorBoard(log_dir=pathLogsTF)
        ])