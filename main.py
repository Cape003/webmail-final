#Importation des bibliothèque nécessaires
from msgError import printE
# Facilite les message d'erreur
#Syntaxe  = printE("le message", nombre de 1 a 3) 
# 1 = succes, 2 = une information importante, 3 = une erreur
import random as r
import subprocess
from datetime import date
from datetime import datetime
import csv
import sqlite3


try: 
    from flask import Flask
    printE("Flask importation success",1)
    #installation de la bibliothèque flask si elle n'est pas déjà présente
except ImportError :
    try : 
        subprocess.run("pip install flask", check=True, shell=True)
        printE("Flask importation is a success",1)
    except subprocess.CalledProcessError as e:
        printE(f"Instalation of Flask failed, instal Flask manualy",3)
          
#---------------------------------------------------------------------------#

today = date.today().isoformat()
try :
    connection = sqlite3.connect("file:Webbase.db?mode=rw", uri = True)
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    printE("Connection to the dadtabase is a success",1)
except sqlite3.Error as e:
    printE(f"SQL error : {e}",3)
    exit()

#La classe groupe permet de gérer la création, suppression et MAJ des groupes
class Groupe:
    def __init__(self,cursor):
        self.cursor = cursor
    
    #Création de groupes
    def create(self,creator):
        #Créée le groupe et ajouter son créateur dans celui-ci
        pin = r.randint(10000,99999)
        self.cursor.execute("INSERT INTO groups (groups_pin, groups_creation, groups_lastUse) VALUES (?, ?, ?)",
        (str(pin), today, today))

        self.cursor.execute("INSERT INTO groups_user (user_id, groups_pin) VALUES (?, ?)",
        (str(creator),str(pin)))
        connection.commit()
    
    #Suppression de groupes
    def pop(self,pin):
        #Vérifi si le groupe que l'on veut supprimer existe 
        self.cursor.execute("SELECT groups_creation FROM groups WHERE groups_pin = ?", (str(pin),))
        r = self.cursor.fetchone()
        if r == None :
            printE("No groups find", 2)
        else:
            #Supp le groupe et ces utilisateurs
            self.cursor.execute("DELETE FROM groups_user WHERE groups_pin = ?",
            (str(pin),))        
            connection.commit()
            self.cursor.execute("DELETE FROM groups WHERE groups_pin = ?",
            (str(pin),))
            connection.commit()
    
    #MAJ de groupes
    def update(self,pin):
        self.cursor.execute("UPDATE groups SET groups_lastUse = ? WHERE groups_pin = ?",(today,str(pin)))
        connection.commit()

#La classe permet de gérers les utilisateur avec la possibilitée de les crééer, de ce connecter a un compte déja existant et de se connecter et deconnecter de groupes
class User:
    def __init__(self,cursor):
        self.cursor = cursor
    
    #Création d'utilisateurs /!\ Faire le sys de hachage de mdp
    def create(self,username,password_hash):
        self.cursor.execute("INSERT INTO mlg_user (user_name, user_password) VALUES (?,?)", (username,str(password_hash)))
        connection.commit()
    
    #login de l'utilisateur (a voir comment l'utiliser dans le future)
    def login(self,username,password_hash):
        self.cursor.execute("SELECT user_id FROM mlg_user WHERE user_name = ? AND user_password = ?", (username,str(password_hash)))

        result = self.cursor.fetchone()
        if result is not None :
            printE(f"Voici l'id demandée : {result[0]}", 2)
        connection.commit()

    #Connexion et déconnexion de groupes
    def connect(self,pin,id):
        self.cursor.execute("INSERT INTO groups_user (user_id, groups_pin) VALUES (?,?)",(int(id),str(pin)))
        connection.commit()
        Groupe.update(pin=pin)

    def disconnect(self,pin,id):
        self.cursor.execute("DELETE FROM groups_user WHERE user_id = ? AND groups_pin = ?",(int(id),str(pin)))
        connection.commit()

#La classe gérant l'envoie et la réception de message dans les différents groupes        
class Messaging:
    def __init__(self,cursor) :
        self.cursor = cursor
    #Permet d'ajouter les messages envoyées sur la bdd
    def send(self,sender_id,groupe_pin,content):
        timestemp = datetime.now().timestamp()
        self.cursor.execute("INSERT INTO messages (user_id, groups_pin, message_sendtime, message_content) VALUES (?,?,?,?)",(int(sender_id),str(groupe_pin),int(timestemp),str(content)))
        connection.commit()

#La classe qui permet de notifier la création d'un groupe ou de demender a en rejoindre un a un utilisateur considéere comme "amis"
class Ping:
    def __init__(self,cursor):
        self.cursor = cursor
    def send(self,sender_id,reciver_id,groups_pin):
        self.cursor.execute("INSERT INTO ping (sender_id, reciver_id, groups_pin, accepted)(?,?,?,?)",((int(sender_id)),int(reciver_id)),str(groups_pin),None)
        connection.commit()
    def accepte(self, ping_id):
        self.cursor.execute('UPDATE ping SET accepted = ? WHERE ping_id = ? ', (bool(True),int(ping_id)))
    def decline(self, ping_id):
        self.cursor.execute('UPDATE ping SET accepted = ? WHERE ping_id = ? ', (bool(False),int(ping_id)))

g = Groupe(cursor)

u = User(cursor)
u.disconnect(44051,2)



connection.close()
