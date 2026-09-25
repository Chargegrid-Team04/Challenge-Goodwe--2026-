import os
import sys

os.chdir('c:/Users/Ioo/Develop/Challenge-Goodwe--2026-')
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from chat_app import demo

config = str(demo.get_config())
print('GoodWe IA Chat' in config)
print('Calcular previsão' in config)
print('Previsão de recarga' in config)
