# -*- coding: utf-8 -*-
"""recommend_keras_mf.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1AN_LJoJzMX8iZW4S4AAYy5mPwwbP3FLd

# Install & Import modules
"""

!pip install keras

import os, codecs, gc
import pandas as pd
import codecs
import numpy as np
import matplotlib.pyplot as plt
import warnings
import keras
from keras import regularizers
from keras.layers import Input, Embedding, Flatten, merge, Dense, Dropout, Lambda, dot
from keras.models import Model
from keras.utils.vis_utils import model_to_dot
from keras.constraints import non_neg
from keras.callbacks import ModelCheckpoint, EarlyStopping, TerminateOnNaN
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
warnings.filterwarnings('ignore')

# mount google my drive
from google.colab import drive
drive.mount('/content/drive')
input_dir = "drive/My Drive/input/"

"""# Load data-file
 Book-Crossing Dataset  
 http://www2.informatik.uni-freiburg.de/~cziegler/BX/
"""

# make dataframe from user data
with codecs.open(input_dir + "BX-Users.csv", "r", "utf8", "ignore") as file:
    user = pd.read_csv(file, delimiter=";")

# make dataframe from items data
col_name = ["ISBN", "Title", "Author", "Year", "Publisher", "URL-S", "URL-M", "URL-L"]
with codecs.open(input_dir + "BX-Books.csv", "r", "utf8", "ignore") as file:
    item = pd.read_csv(file, delimiter=";", names=col_name, skiprows=1, converters={"Year" : str})

# make dataframe from rating data
with codecs.open(input_dir + "BX-Book-Ratings.csv", "r", "utf8", "ignore") as file:
    rating = pd.read_csv(file, delimiter=";")

"""# data cleaning"""

# join dataframe item & rating
rating_author = pd.merge(rating, item, how='left', on='ISBN')

rating_author.head()

# select user-ID, Author, Book-Rating, Year
rating_author = rating_author.iloc[:, [0, 4, 2, 5]]

# drop nan
rating_author.dropna(inplace=True)
rating_author = rating_author[rating_author.Year.str.contains(pat='\d', regex=True)].iloc[:, 0:3]

"""# arrange dataset"""

# calc rating by user and author 
data = rating_author.groupby(['User-ID', 'Author'])["Book-Rating"].agg(['mean']).reset_index()
data.sort_values(by=['User-ID', 'Author'], inplace=True)
data.columns = ["userID", "author", "raw_ratings"]

data.raw_ratings = data.raw_ratings.astype("int")

del user, item, rating, rating_author
gc.collect()

"""# make dataset for keras"""

# convert to category
data["user_category"] = data.userID.astype('category').cat.codes.values
data["author_category"] = data.author.astype('category').cat.codes.values

data.head()

# binning raw_ratings
data.raw_ratings = data.raw_ratings.apply(lambda x : 0 if x == 0 else (1 if x in [1,2,3,4]  else (2 if x in[5, 6, 7] else 3)))

X = data.drop(['userID', 'author', 'raw_ratings'], axis=1)
y = data.raw_ratings

"""# Define training function"""

def train_keras(model):
  k = 5
  for i in range(k):
    print("===========Round" + str(i) + " Start===========" )
    train_x, test_x, train_y, test_y = train_test_split(X, y, test_size=0.1, random_state=i)
  
    model.fit([train_x.user_category, train_x.author_category],  train_y,  epochs=10, validation_split=0.2,
              callbacks=[mcheck, echeck, ncheck], verbose=1)
  
    model.evaluate([test_x.user_category, test_x.author_category], test_y, verbose=1)
    pred = model.predict([test_x.user_category, test_x.author_category])
  
    print(np.sqrt(mean_squared_error(test_y, pred)))

"""# make network for Keras MF & Training"""

n_users, n_author = len(data.user_category.unique()), len(data.author_category.unique())
n_latent_factors = 3

# define metrics
from keras import backend as K
def rmse(y_true, y_pred):
        return K.sqrt(K.mean(K.square(y_pred - y_true), axis=-1))

# author network
author_input = keras.layers.Input(shape=[1], name='author')
author_embedding = keras.layers.Embedding(n_author + 1, n_latent_factors, name='author-Embedding')(author_input)
author_vec = keras.layers.Flatten(name='flatten_author')(author_embedding)
author_vec = keras.layers.Dropout(0.2)(author_vec)

# user network
user_input = keras.layers.Input(shape=[1],name='User')
user_embedding = keras.layers.Embedding(n_author + 1, n_latent_factors, name='user-Embedding')(user_input)
user_vec = keras.layers.Flatten(name='flatten_users')(user_embedding)
user_vec = keras.layers.Dropout(0.2)(user_vec)

# concat author and user
concat_vec = keras.layers.concatenate([author_vec, user_vec], axis=-1)
concat_vec = keras.layers.Dropout(0.2)(concat_vec)

# full-connected
dense4 = keras.layers.Dense(4, name='FullyConnected1', activation='relu')(concat_vec)
result = keras.layers.Dense(1, activation='relu',name='Activation')(dense4)
model = keras.Model([user_input, author_input], result)
model.compile(optimizer='Adagrad', loss='mse', metrics=[rmse])

# define callback
mcheck = ModelCheckpoint(filepath="./recommend.h5", monitor='val_loss', save_best_only=True)
echeck = EarlyStopping(monitor='val_loss', patience=0, verbose=0, mode='auto')
ncheck = TerminateOnNaN()

train_keras(model)

"""# make network for Keras NMF & Training"""

from keras.constraints import non_neg

# author network
author_input = keras.layers.Input(shape=[1], name='author')
author_embedding = keras.layers.Embedding(n_author + 1, n_latent_factors, name='author-Embedding', embeddings_constraint=non_neg())(author_input)
author_vec = keras.layers.Flatten(name='flatten_author')(author_embedding)
author_vec = keras.layers.Dropout(0.2)(author_vec)

# user network
user_input = keras.layers.Input(shape=[1],name='User')
user_embedding = keras.layers.Embedding(n_author + 1, n_latent_factors, name='user-Embedding', embeddings_constraint=non_neg())(user_input)
user_vec = keras.layers.Flatten(name='flatten_users')(user_embedding)
user_vec = keras.layers.Dropout(0.2)(user_vec)

# concat author and user
concat_vec = keras.layers.concatenate([author_vec, user_vec], axis=-1)
concat_vec = keras.layers.Dropout(0.2)(concat_vec)

# full-connected
dense4 = keras.layers.Dense(4, name='FullyConnected1', activation='relu')(concat_vec)
result = keras.layers.Dense(1, activation='relu',name='Activation')(dense4)
model = keras.Model([user_input, author_input], result)
model.compile(optimizer='Adagrad', loss='mse', metrics=[rmse])

train_keras(model)

