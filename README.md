# Judge worker for [CARP-OJ](https://github.com/edwardfang/CARP-OJ)

## Requirements
- Linux
- Docker
- Python 3.6+

## Config
Refer to [config-example.py](./config-example.py).

## Install
1. Create or import docker image [carp_judge](https://drive.google.com/open?id=1aNCdWFg2yVq-s0bQlsGMy4SJoGH9Qidd).  
*It's just minimal debian with python3 and numpy installed.*
2. `pip install -r requirements.txt`

## Run
```sh
sudo python3 main.py
```
