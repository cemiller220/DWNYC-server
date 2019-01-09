from flask import Flask, jsonify, request, redirect, url_for
from flask_cors import CORS
import pandas as pd
import json
from datetime import datetime
from firebase import firebase

# configuration
DEBUG = True

# instantiate the app
app = Flask(__name__)
app.config.from_object(__name__)
fb = firebase.FirebaseApplication('https://dwnyc-29204.firebaseio.com', None)

# enable CORS
CORS(app)

season = 'season14'


def firebase_get(season, field):
    res = fb.get('%s/%s'%(season,field), None)
    return res


def firebase_put(season, field, data):
    fb.put(season, field, data)


choreographers = firebase_get(season, 'choreographers')
times = firebase_get(season, 'times')


def reformat_cast_list(casting):
    res = []
    for i, dance in enumerate(casting['Dance'].unique()):
        r = {'name': dance, 'choreographer': choreographers[dance], 'time': times[dance]}
        r['cast'] = list(sorted(casting[(casting['Dance'] == dance) & (casting['Status'] != 'Waitlist')]['Name'].values))
        r['waitlist'] = list(casting[(casting['Dance'] == dance) & (casting['Status'] == 'Waitlist')]['Name'].values)
        res.append(r)
    return res


@app.route('/get_cast_list', methods=['GET'])
def get_cast_list():
    casting = pd.DataFrame(firebase_get(season, '/cast_list'))
    #casting = pd.read_csv('casting.csv')
    res = reformat_cast_list(casting)
    return jsonify(res)


@app.route('/get_dances', methods=['GET'])
def get_dances():
    casting = pd.DataFrame(firebase_get(season, '/cast_list'))
    #casting = pd.read_csv('casting.csv')
    dances = list(casting['Dance'].unique())
    return jsonify(dances)


@app.route('/get_show_order', methods=['GET'])
def get_show_order():
    show_order = {i: dance for i, dance in enumerate(firebase_get(season, 'show_order'))}
    # with open('show_order.json', 'r') as fp:
    #     show_order = json.load(fp)
    return jsonify(show_order)


@app.route('/save_show_order', methods=['POST'])
def save_show_order():
    show_order = json.loads(request.data)
    print(show_order)
    firebase_put(season, 'show_order', show_order)
    # with open('show_order.json', 'w') as fp:
    #     json.dump(show_order, fp)
    return '', 204


@app.route('/get_available_dances', methods=['GET'])
def get_available_dances():
    last_dance = request.args.get('last_dance', '')
    next_dance = request.args.get('next_dance', '')
    print(last_dance, next_dance)
    allowed_next = firebase_get(season, 'allowed_next_dances')
    # with open('allowed_next_dances.json', 'r') as fp:
    #     allowed_next = json.load(fp)

    if (last_dance == '' or last_dance == 'INTERMISSION') and (next_dance == '' or next_dance == 'INTERMISSION'):
        casting = pd.DataFrame(firebase_get(season, 'cast_list'))
        # casting = pd.read_csv('casting.csv')
        dances = list(casting['Dance'].unique())
        return jsonify(dances)
    elif last_dance == '' or last_dance == 'INTERMISSION':
        return jsonify(allowed_next[next_dance]['include_style'])
    elif next_dance == '' or next_dance == 'INTERMISSION':
        return jsonify(allowed_next[last_dance]['include_style'])
    else:
        return jsonify(list(set(allowed_next[next_dance]['include_style']).intersection(allowed_next[last_dance]['include_style'])))


@app.route('/get_dancer', methods=['GET'])
def get_dancer():
    casting = pd.DataFrame(firebase_get(season, 'cast_list'))
    # casting = pd.read_csv('casting.csv')
    dancer = request.args.get('dancer', '')
    casting = casting[casting['Name'].str.contains(dancer)]
    res = reformat_cast_list(casting)
    return jsonify(res)


@app.route('/get_dance', methods=['GET'])
def get_dance():
    casting = pd.DataFrame(firebase_get(season, 'cast_list'))
    # casting = pd.read_csv('casting.csv')
    dance = request.args.get('dance', '')
    casting = casting[casting['Dance'] == dance]
    res = reformat_cast_list(casting)
    return jsonify(res)


@app.route('/filter_data', methods=['GET'])
def filter_data():
    casting = pd.DataFrame(firebase_get(season, 'cast_list'))
    # casting = pd.read_csv('casting.csv')
    print(request.args)
    dance = request.args.get('dance', '')
    dancer = request.args.get('dancer', '')
    print(dance)
    print(dancer)
    if dance == '':
        casting = casting[casting['Name'].str.contains(dancer)]
    elif dancer == '':
        casting = casting[casting['Dance'] == dance]
    else:
        casting = casting[(casting['Dance'] == dance) & (casting['Name'].str.contains(dancer))]
    res = reformat_cast_list(casting)
    return jsonify(res)


@app.route('/reset_casting', methods=['GET'])
def reset_casting():
    firebase_put(season, 'cast_list', firebase_get(season, 'original_cast_list'))
    # pd.read_csv('casting_orig.csv').to_csv('casting.csv', index=False)
    return '', 204


@app.route('/drop_dancer', methods=['GET'])
def drop_dancer():
    dancer = request.args.get('dancer', '')
    dance = request.args.get('dance', '')

    casting = pd.DataFrame(firebase_get(season, 'cast_list'))
    # casting = pd.read_csv('casting.csv')
    casting = casting.drop(casting[(casting['Dance'] == dance) & (casting['Name'] == dancer)].index)
    firebase_put(season, 'cast_list', casting.to_dict(orient='records'))
    # casting.to_csv('casting.csv', index=False)
    res = reformat_cast_list(casting)
    return jsonify(res)


@app.route('/add_dancer', methods=['GET'])
def add_dancer():
    dancer = request.args.get('dancer', '')
    dance = request.args.get('dance', '')
    add_type = request.args.get('add_type', '')

    casting = pd.DataFrame(firebase_get(season, 'cast_list'))
    # casting = pd.read_csv('casting.csv')
    if add_type == 'from_waitlist':
        casting.at[casting[(casting['Dance'] == dance) & (casting['Name'] == dancer)].index, 'Status'] = 'Cast'
    elif add_type == 'new_cast':
        casting = casting.append(pd.DataFrame([[dance, dancer, 'Cast']], columns=casting.columns))
    elif add_type == 'new_waitlist':
        casting = casting.append(pd.DataFrame([[dance, dancer, 'Waitlist']], columns=casting.columns))
    else:
        raise ValueError('Invalid Add Type: %s'%add_type)

    firebase_put(season, 'cast_list', casting.to_dict(orient='records'))
    #casting.to_csv('casting.csv', index=False)
    res = reformat_cast_list(casting)
    return jsonify(res)


@app.route('/get_quick_changes', methods=['GET'])
def get_quick_change():
    quick_changes = firebase_get(season, 'quick_changes')
    # with open('quick_changes.json', 'r') as fp:
    #     quick_changes = json.load(fp)

    return jsonify(quick_changes)


@app.route('/get_change_log', methods=['GET'])
def get_change_log():
    change_log = firebase_get(season, 'change_log')
    # with open('change_log.json', 'r') as fp:
    #     change_log = json.load(fp)
    return jsonify(change_log)


@app.route('/add_to_change_log', methods=['POST'])
def add_to_change_log():
    new_change = json.loads(request.data)
    date = str(datetime.now().date())
    print('adding to change log - %s' % date)

    change_log = firebase_get(season, 'change_log')
    # with open('change_log.json', 'r') as fp:
    #     change_log = json.load(fp)

    updated = False
    for i, change_date in enumerate(change_log):
        print(i)
        print(change_date['date'])
        if change_date['date'] == date:
            change_log[i]['changes'].insert(0, new_change)
            updated = True
            break

    if not updated:
        print('Not updated. Appending new date')
        change_log.insert(0, {'date': date, 'changes': [new_change]})

    firebase_put(season, 'change_log', change_log)
    # with open('change_log.json', 'w') as fp:
    #     json.dump(change_log, fp)

    return '', 204


@app.route('/undo_change', methods=['POST'])
def undo_change():
    change = json.loads(request.data)

    change_log = firebase_get(season, 'change_log')
    # with open('change_log.json', 'r') as fp:
    #     change_log = json.load(fp)

    for i, change_date in enumerate(change_log):
        if change_date['date'] == change['date']:
            change_log[i]['changes'] = [d for d in change_log[i]['changes'] if d.get('type') != change['change']['type'] and d.get('name') != change['change']['name'] and d.get('dance') != change['change']['dance']]
            if len(change_log[i]['changes']) == 0:
                change_log = [d for j, d in enumerate(change_log) if j != i]
            break

    firebase_put(season, 'change_log', change_log)
    # with open('change_log.json', 'w') as fp:
    #     json.dump(change_log, fp)

    print(change['change']['type'])
    if change['change']['type'] == 'Added':
        return redirect(url_for('add_dancer', dancer=change['change']['name'], dance=change['change']['dance'], add_type='new_waitlist'))
    elif change['change']['type'] == 'Dropped':
        return redirect(url_for('add_dancer', dancer=change['change']['name'], dance=change['change']['dance'], add_type='new_cast'))


if __name__ == '__main__':
    app.run()
