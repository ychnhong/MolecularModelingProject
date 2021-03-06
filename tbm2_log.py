import numpy as np
import math
import Bio.PDB as pdb

import matplotlib as mpl
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import matplotlib.pyplot as plt



def distance(point1, point2):
    squareDistance = np.sum((point1 - point2)**2, axis=0)
    sqrtDistance = np.sqrt(squareDistance)
    return sqrtDistance

def pdf(tarDistance, temDistance, sigma):
    prob = 1/(sigma * np.sqrt(2*math.pi)) * np.exp(-1/2*((tarDistance - temDistance)/sigma)**2)
    return prob

def objProb(tarPoints, temPoints, temW, sigma):
    # Get number of points, and number of templates
    nTarPts = tarPoints.shape[0]
    nTemplates = temPoints.shape[0]
    nTemPts = temPoints.shape[1]

    # Array to store distances
    tarDisArray = np.zeros((nTarPts, nTarPts))
    temDisArray = np.zeros((nTemplates, nTemPts, nTemPts))
    cacheArray = np.zeros((nTemplates, nTemPts, nTemPts))
    # Array to store pdf
    pdfArray = np.zeros((nTemplates, nTarPts, nTarPts))

    # Compute distances between Target Atoms, and between Template Atoms
    for i in range(0,nTarPts-1):
        for j in range(i+1,nTarPts):
            tarDisArray[i,j] = distance(tarPoints[i,:], tarPoints[j,:])
            # tarDisArray[j,i] = tarDisArray[i,j]
    for k in range(0,nTemplates):
        for i in range(0,nTemPts-1):
            for j in range(i+1,nTemPts):
                temDisArray[k,i,j] = distance(temPoints[k,i,:], temPoints[k,j,:])
                # temDisArray[k,j,i] = temDisArray[k,i,j]
                
    # Compute pdf
    for k in range(0,nTemplates):
        for i in range(0,nTarPts-1):
            for j in range(i+1,nTarPts):
                pdfArray[k,i,j] = temW[k] * pdf(tarDisArray[i,j], temDisArray[k,i,j], sigma)
                # pdfArray[k,j,i] = pdfArray[k,i,j]
                cacheArray[k,i,j] = pdfArray[k,i,j] * (tarDisArray[i,j] - temDisArray[k,i,j]) / (sigma**2) # for gradient calculation

    # Sum pdf over k templates for each distance:
    sumPdf = np.sum(pdfArray, axis=0)
    sumCache = np.sum(cacheArray, axis=0) # for gradient calculation

    # Multiply over half of sumPdf (not include diagonal):
    upperPdf_noDiag = np.triu(sumPdf, k=1)
    productPdf = np.prod(upperPdf_noDiag[upperPdf_noDiag > 0])

    # Log
    # logPdf = - np.log(productPdf)
    logArray = -np.log(upperPdf_noDiag[upperPdf_noDiag > 0])
    logPdf = np.sum(logArray)
    print('logPdf: ', logPdf)

    return tarDisArray, temDisArray, pdfArray, sumPdf, sumCache, productPdf, logPdf

def gradient(tarPoints, tarDisArray, sumPdf, sumCache):
    nTar = tarDisArray.shape[0]

    gradFd = np.zeros(tarDisArray.shape)
    # gradFx = np.zeros((nTar,1))
    # gradFy = np.zeros((nTar,1))
    # gradFz = np.zeros((nTar,1))
    gradFpoints = np.zeros((nTar,3))

    gradFd = (1/sumPdf) * sumCache
    # print('gradFd: ')
    # print(gradFd)

    for i in range(0,nTar):
        if (i < nTar-1):
            # gradFx[i] = gradFd[i,i+1] * (tarPoints[i,0] - tarPoints[i+1,0])/tarDisArray[i,i+1]
            # gradFy[i] = gradFd[i,i+1] * (tarPoints[i,1] - tarPoints[i+1,1])/tarDisArray[i,i+1]
            # gradFz[i] = gradFd[i,i+1] * (tarPoints[i,2] - tarPoints[i+1,2])/tarDisArray[i,i+1]
            gradFpoints[i] = gradFd[i,i+1] * (tarPoints[i] - tarPoints[i+1])/tarDisArray[i,i+1]
        else:
            # gradFx[i] = gradFd[1,i] * (tarPoints[i,0] - tarPoints[1,0])/tarDisArray[1,i]
            # gradFy[i] = gradFd[1,i] * (tarPoints[i,1] - tarPoints[1,1])/tarDisArray[1,i]
            # gradFz[i] = gradFd[1,i] * (tarPoints[i,2] - tarPoints[1,2])/tarDisArray[1,i]
            gradFpoints[i] = gradFd[1,i] * (tarPoints[i] - tarPoints[1])/tarDisArray[1,i]
    # gradFpoints = np.hstack((gradFx, gradFy, gradFz))
    return gradFd, gradFpoints


def gradDescent(tarPoints0, temPoints, temW, sigma, alpha=0.05, tolerance=10**(-5), maxiter=200):

    tarPoints = tarPoints0
    tarDisArray, temDisArray, pdfArray, sumPdf, sumCache, productPdf, logPdf = objProb(tarPoints, temPoints, temW, sigma)
    iter = 0
    error = 0.5
    while (iter < maxiter) and (error > tolerance):

        gradFd, gradFpoints = gradient(tarPoints, tarDisArray, sumPdf, sumCache)
        tarPoints += - alpha*gradFpoints

        new_tarDisArray, new_temDisArray, new_pdfArray, new_sumPdf, new_sumCache, new_productPdf, new_logPdf = objProb(tarPoints, temPoints, temW, sigma)

        error = abs(logPdf - new_logPdf)

        if  error < tolerance:
            return tarPoints
        else:
            tarDisArray = new_tarDisArray
            sumPdf = new_sumPdf
            sumCache = new_sumCache
            logPdf = new_logPdf

        iter += 1
        print('iteration: ', iter, '        error: ', error)

    return tarPoints

def getTemplate(temFile):
    parser = pdb.PDBParser()
    struct = parser.get_structure('template', temFile)

    temPoints = list()
    for model in struct:
        for chain in model:
            for res in chain:
                for atom in res:
                   if (atom.name == 'CA'):
                        vector = atom.get_vector()
                        temPoints.append(list(vector))

    return np.array(temPoints)

def writePoints(inFile, outFile, optimalPoints):
    parser = pdb.PDBParser()
    struct = parser.get_structure('target', inFile)

    optimalPoints = np.array(optimalPoints)
    i = 0

    for model in struct:
        for chain in model:
            for res in chain:
                for atom in res:
                    if (atom.name == 'CA'):
                        atom.coord = optimalPoints[i,:]
                        i += 1


    io = pdb.PDBIO()
    io.set_structure(struct)
    io.save(outFile)
    return

def showProtein():

    return

def showFunction():

    return


def main():
    nseed = 1
    np.random.seed(nseed)
    # tarPoints = np.random.randint(30, size=(5,3))/30.0
    # temPoints = np.random.randint(30, size=(2,5,3))/30.0
    tarFile = '1fdx.B99990001.pdb'
    temFile = '5fd1.pdb'
    outFile = 'new_out.pdb'
    
    temPoints0 = getTemplate(temFile)
    tem1 = temPoints0[0:8, :]
    tem2 = temPoints0[10:28, :]
    tem3 = temPoints0[30:58, :]
    temPoints = np.vstack((tem1, tem2, tem3))

    tarPoints = temPoints - np.random.rand(temPoints.shape[0], temPoints.shape[1])*10
    temPoints = np.reshape(temPoints, (1,temPoints.shape[0], temPoints.shape[1]))
    # tarPoints = np.random.randint(15, 20, size=(temPoints.shape[1],3))/1.0

    # tarPoints = tarPoints.astype(float)
    # temPoints = temPoints.astype(float)

    # temW = [0.4, 0.6]
    temW = [1.0]

    sigma = 0.5

    optimalTarget = gradDescent(tarPoints, temPoints, temW, sigma, alpha=0.01, tolerance=10**(-5), maxiter=1000)
    print('optimalTarget: \n', optimalTarget)

    # %% VISUALIZE
    mpl.rcParams['legend.fontsize'] = 10
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    ax.plot(temPoints[0,:,0], temPoints[0,:,1], temPoints[0,:,2], label='template')
    ax.plot(optimalTarget[:,0], optimalTarget[:,1], optimalTarget[:,2], label='target approximation')
    ax.legend(['Template','Target Fit'])
    fig.savefig('new_out.png')
    plt.show()


    writePoints(tarFile, outFile, optimalTarget)

    return



if __name__ == '__main__':
    main()





    




    










