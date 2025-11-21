import time
import threading
import requests
import socketio
import random

BASE = 'http://localhost:5000'

sio_clients = {}

# Utility to register user via HTTP
def http_register(username, password='test123'):
    r = requests.post(BASE + '/register', json={'username': username, 'password': password})
    print('register', username, r.status_code, r.text)

class TestClient:
    def __init__(self, name):
        self.name = name
        self.sio = socketio.Client()
        self.state = {}
        self._wire()

    def _wire(self):
        @self.sio.event
        def connect():
            print(f"[{self.name}] connected")
            self.sio.emit('register_user', self.name)

        @self.sio.event
        def disconnect():
            print(f"[{self.name}] disconnected")

        @self.sio.on('bb84_qubits')
        def on_qubits(data):
            print(f"[{self.name}] received bb84_qubits from", data.get('from'))
            qubits = data.get('qubits', [])
            N = len(qubits)
            meas_bases = [ '+' if random.random()<0.5 else 'x' for _ in range(N) ]
            measured = []
            for i,q in enumerate(qubits):
                if meas_bases[i] == q.get('basis'):
                    measured.append(q.get('bit'))
                else:
                    measured.append(1 if random.random()<0.5 else 0)
            self.state['meas_bases'] = meas_bases
            self.state['measured'] = measured
            # send back measurements
            self.sio.emit('bb84_measurements', {'from': self.name, 'to': data.get('from'), 'bases': meas_bases, 'measured': measured})
            print(f"[{self.name}] sent measurements to {data.get('from')}")

        @self.sio.on('bb84_measurements')
        def on_measurements(data):
            # initiator receives this
            sender = data.get('from')
            print(f"[{self.name}] got bb84_measurements from {sender}")
            state = self.state
            if state.get('role') != 'initiator':
                state['received_meas_bases'] = data.get('bases')
                state['received_measured'] = data.get('measured')
                return
            # send bases reveal
            self.sio.emit('bb84_bases_reveal', {'from': self.name, 'to': sender, 'bases': state['bases']})
            state['received_meas_bases'] = data.get('bases')
            state['received_measured'] = data.get('measured')
            print(f"[{self.name}] sent bb84_bases_reveal to {sender}")

        @self.sio.on('bb84_bases_reveal')
        def on_bases_reveal(data):
            # receiver receives initiator bases
            sender = data.get('from')
            print(f"[{self.name}] got bb84_bases_reveal from {sender}")
            # reply with our bases (sample reveal event used for that in client)
            my_bases = self.state.get('meas_bases')
            self.sio.emit('bb84_sample_reveal', {'from': self.name, 'to': sender, 'bases': my_bases})
            self.state['their_bases'] = data.get('bases')
            print(f"[{self.name}] sent my bases back to {sender}")

        @self.sio.on('bb84_sample_reveal')
        def on_sample_reveal(data):
            # This handler will be used both for initiator receiving the receiver's bases and for the actual sample exchange
            if 'sample' not in data:
                # it's bases from receiver
                sender = data.get('from')
                print(f"[{self.name}] got receiver bases from {sender}")
                return
            # else it's the sample pairs
            print(f"[{self.name}] got sample for testing from {data.get('from')}")
            sample = data.get('sample')
            # compute mismatches
            mismatches = sum(1 for p in sample if p.get('initiator_bit') != p.get('receiver_bit'))
            e_rate = mismatches / max(1, len(sample))
            passed = e_rate <= 0.15
            print(f"[{self.name}] sample mismatches={mismatches} e_rate={e_rate:.2f} passed={passed}")
            # send result back
            self.sio.emit('bb84_result', {'from': self.name, 'to': data.get('from'), 'e_rate': e_rate, 'passed': passed})

        @self.sio.on('bb84_result')
        def on_result(data):
            print(f"[{self.name}] final bb84_result: {data}")

        @self.sio.on('bb84_eavesdrop_capture')
        def on_eavesdrop_capture(data):
            print(f"[{self.name}] eavesdrop capture received: {data}")

    def connect(self):
        self.sio.connect('http://localhost:5000')

    def disconnect(self):
        self.sio.disconnect()

    def start_initiator(self, to, N=128, sampleSize=32):
        bits = [1 if random.random()<0.5 else 0 for _ in range(N)]
        bases = ['+' if random.random()<0.5 else 'x' for _ in range(N)]
        qubits = [{'i':i,'bit':bits[i],'basis':bases[i]} for i in range(N)]
        self.state.update({'role':'initiator','bits':bits,'bases':bases,'N':N,'sampleSize':sampleSize})
        self.sio.emit('bb84_qubits', {'from': self.name, 'to': to, 'qubits': qubits})
        print(f"[{self.name}] initiated BB84 to {to}")


def run_test():
    # ensure server is up (sleep a bit)
    time.sleep(1)
    # create unique user names to avoid conflicts with existing accounts
    suffix = str(int(time.time()))
    alice_name = f'alice_{suffix}'
    bob_name = f'bob_{suffix}'
    eve_name = f'eve_{suffix}'

    # register users
    http_register(alice_name)
    http_register(bob_name)
    http_register(eve_name)

    # create clients
    alice = TestClient(alice_name)
    bob = TestClient(bob_name)
    eve = TestClient(eve_name)

    # connect all (sequentially to avoid polling timeouts)
    alice.connect()
    time.sleep(0.5)
    bob.connect()
    time.sleep(0.5)
    eve.connect()
    time.sleep(1)

    # Eve registers eavesdrop on alice,bob
    eve.sio.emit('register_eavesdrop', {'user1': alice_name, 'user2': bob_name, 'by': eve_name})
    print('[test] eve registered eavesdrop on alice,bob')
    time.sleep(1)

    # Alice initiates BB84 to Bob
    alice.start_initiator('bob', N=128, sampleSize=32)

    # let events flow
    time.sleep(5)

    # cleanup
    alice.disconnect(); bob.disconnect(); eve.disconnect()

if __name__ == '__main__':
    run_test()
