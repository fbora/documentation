from Models import kagglegym
import numpy as np
import pandas as pd
from sklearn import linear_model, ensemble
from sklearn import cluster


def clusterY(rets, nclusters):
    clustertrain = train[['id', 'timestamp', 'y']].pivot(index='timestamp', columns='id')
    clustertrain = clustertrain.xs('y', axis=1, drop_level=True)

    nullCount = pd.isnull(clustertrain).sum(axis=0).reset_index()
    completeId = nullCount[nullCount[0] == 0].id.values
    incompleteId = nullCount[nullCount[0] > 0].id.values
    incompleteCluster = pd.Series((np.ones(len(incompleteId)) * -1).astype(int), index=incompleteId)
    completeDF = clustertrain[completeId]
    kmeans = cluster.KMeans(n_clusters=nclusters, random_state=0).fit(completeDF.T)
    labels = pd.Series(kmeans.labels_, index=completeDF.columns)
    labelcts = labels.value_counts()
    smallcluster = labelcts[labelcts<50].index.values
    if smallcluster: labels.replace(smallcluster, -1, inplace=True)
    labels = labels.append(incompleteCluster)
    return labels


def fitEachCluster(data, clusters):
    modelDict = {}
    for label in np.unique(clusters.values):
        if label != -1:
            ids = clusters[clusters.values==label].index.values
            clusterData = data[data.id.isin(ids)]
        else:
            clusterData = data.copy()
        y = clusterData.y
        X = clusterData.drop(['y'], axis=1)#'id', 'timestamp']
        print('fitting cluster number:', label)
        print('count', sum(clusters==label))
        # model = linear_model.ElasticNetCV(normalize=True, max_iter=100000).fit(X, y)
        model = ensemble.RandomForestRegressor(n_jobs=8).fit(X,y)
        modelDict[label] = model
    return modelDict


def predictY(features, modelDict, clusters):
    ySeries = pd.Series(np.zeros(len(features.index)), index=features.index)
    for label in np.unique(clusters.values):
        model = modelDict[label]
        clusterIds = clusters[clusters.values == label].index.values
        clusterFeatures = features[features.id.isin(clusterIds)]
        if len(clusterFeatures)==0:
            continue
        X = clusterFeatures#.drop(['id', 'timestamp'], axis=1)
        cluster_y = model.predict(X)
        ySeries.loc[X.index] = pd.Series(cluster_y, index=X.index)
    return ySeries


def main():
    # The "environment" is our interface for code competitions
    env = kagglegym.make()

    # We get our initial observation by calling "reset"
    observation = env.reset()

    print("computing predictor models")
    train = observation.train
    mean = train.mean(axis=0)
    train.fillna(mean, axis=0, inplace=True)
    clusters = clusterY(train, 1)

    modelDict = fitEachCluster(train, clusters)


    print("predicting output for timestamps")

    while True:
        target = observation.target
        features = observation.features
        features.fillna(mean, axis=0, inplace=True)
        predicted_y = predictY(features.copy(), modelDict, clusters)
        target.y = predicted_y
        timestamp = observation.features["timestamp"][0]

        if timestamp % 100 == 0:
            print("Timestamp #{}".format(timestamp))
        observation, reward, done, info = env.step(target)
        if done:
            print("Public score: {}".format(info["public_score"]))
            break

if __name__=='__main__':
    main()