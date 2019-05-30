# coding=utf8
import os
import mysql.connector
from datetime import date
from functools import wraps
import requests
import time
# from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor
from itertools import groupby
from dateutil.relativedelta import relativedelta
from collections import OrderedDict

from flask import Flask, json, jsonify, request, abort, render_template
from flask_cors import CORS, cross_origin
import json as json_builtin

import models
import updateModules
import helpers

app = Flask(__name__, static_url_path='/static')
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret')
db_config = {
    'user': os.environ.get('DB_USER', 'test'),
    'password': os.environ.get('DB_PASSWORD', 'testpw'),
    'host': '127.0.0.1',
    'database': os.environ.get('DB_NAME', 'testdb'),
}


# decorator for checking the api-key
def require_appkey(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if request.args.get('key') and request.args.get('key') == app.config['SECRET_KEY']:
            return view_function(*args, **kwargs)
        else:
            abort(401)

    return decorated_function


# Hello World
@app.route('/hello')
@cross_origin()
@require_appkey
def hello_world():
    return jsonify(hell0='world'), 200

# Front End Testing
@app.route('/admin')
@cross_origin()
@require_appkey
def front():
    secret_key = app.config['SECRET_KEY']
    # for filter-selectors.html
    return render_template('admin.html', **{
        'secret_key': secret_key,
        'sessions': helpers.get_current_sessions(),
    })

# Front End Dev Page
@app.route('/front_dev')
@cross_origin()
@require_appkey
def front_dev():
    baseUrlVvzUzh = 'https://studentservices.uzh.ch/uzh/anonym/vvz/index.html#/details/'
    whitelist = []
    blacklist = []
    searchterms = []
    found_modules= []
    studyprograms = {0: "Theologie: Vollstudienfach 120"}
    studyprogramid_moduleids = {0: [2]}
    secret_key = app.config['SECRET_KEY']

    try:
        whitelist = json.loads(get_whitelist().get_data())
        blacklist = json.loads(get_blacklist().get_data())
        searchterms = json.loads(get_searchterms().get_data())
        found_modules = json.loads(search().get_data())
        studyprograms = get_studyprograms().get_data(as_text=True)
        studyprogramid_moduleids = get_studyprograms_modules().get_data(as_text=True)
    except mysql.connector.errors.InterfaceError as e:
        print(e, "\n!!!only works on server!!!")
        test = {
            'PiqSession': 3,
            'PiqYear': 2018,
            'SmObjId': 50904112,
            'title': "ayy",
            'whitelisted': 1,
        }
        whitelist.append(test)
        blacklist.append(test)
        found_modules.append(test)
        searchterms.append({"id": 1, "term": "wut"})

    return render_template('front_dev.html', **{
        'whitelist': whitelist,
        'blacklist': blacklist,
        'searchterms': searchterms,
        'baseUrlVvzUzh': baseUrlVvzUzh,
        'secret_key': secret_key,
        'found_modules': found_modules,
        # for filter-selectors.html
        'sessions': helpers.get_current_sessions(),
        'studyprogramid_moduleids': studyprogramid_moduleids,
        'studyprograms': studyprograms,
    })

@app.route('/public')
@cross_origin()
@require_appkey
def public():
    studyprograms = {0: "Theologie: Vollstudienfach 120"}
    studyprogramid_moduleids = {0: [2]}
    secret_key = app.config['SECRET_KEY']

    try:
        studyprograms = get_studyprograms().get_data(as_text=True)
        studyprogramid_moduleids = get_studyprograms_modules().get_data(as_text=True)
    except mysql.connector.errors.InterfaceError as e:
        print("not possible in dev", e)

    return render_template('public.html', **{
        'secret_key': secret_key,
        # for filter-selectors.html
        'sessions': helpers.get_current_sessions(),
        'studyprogramid_moduleids': studyprogramid_moduleids,
        'studyprograms': studyprograms,
    })



# Information about the API
@app.route('/')
@cross_origin()
def info():
    return 'This is a small scale API to access and manipulate data about Sustainability-related Modules at the University of Zurich'

# update all modules
@app.route('/update')
@cross_origin()
def update():
    if updateModules.update_db():
        return 'modules updated', 200
    else:
        return 'error', 400


# get whitelist
@app.route('/modules/whitelist', methods=['GET'])
@cross_origin()
def get_whitelist():
    return get_modules(whitelisted=1)

def get_modules(whitelisted):
    modules = []
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor(dictionary=True)
    qry = (
        "SELECT * FROM module as m WHERE whitelisted = {whitelisted} ORDER BY title ASC".format(whitelisted=whitelisted))
    cursor.execute(qry)
    for module in cursor:
        for column, value in module.items():
            if type(value) is bytearray:
                module[column] = value.decode('utf-8')
        modules.append(module)
    cnx.close()
    return jsonify(modules)

@app.route('/modules', methods=['POST'])
@cross_origin()
@require_appkey
def add_module(): # required: SmObjId, PiqYear, PiqSession, whitelisted, searchterm
    req_data = request.get_json()
    SmObjId = req_data['SmObjId']
    PiqYear = req_data['PiqYear']
    PiqSession = req_data['PiqSession']
    whitelisted = int(req_data['whitelisted'])
    searchterm = req_data['searchterm']
    m = models.Module(SmObjId)
    module_values = m.find_module_values(PiqYear, PiqSession)
    if module_values is not None:
        try:
            cnx = mysql.connector.connect(**db_config)
            qry = "INSERT INTO module (SmObjId, PiqYear, PiqSession, title, whitelisted, searchterm) VALUES (%(SmObjId)s, %(PiqYear)s, %(PiqSession)s, %(title)s, %(whitelisted)s, %(searchterm)s) ON DUPLICATE KEY UPDATE whitelisted=%(whitelisted)s"
            module_values['whitelisted'] = whitelisted
            module_values['searchterm'] = searchterm
            cursor = cnx.cursor()
            cursor.execute(qry, module_values)
            module_id = cursor.lastrowid
            if module_id == 0:
                cursor.execute("SELECT id FROM module WHERE SmObjId = %(SmObjId)s AND PiqYear = %(PiqYear)s AND PiqSession=%(PiqSession)s", module_values)
                for row in cursor:
                    print("module_id = cursor.lastrowid did not work", row)
                    module_id = row[0]
            cnx.commit()
            cursor.close()

            # if a module is to be saved, find the corresponding studyprograms and save them too
            studyprograms = find_studyprograms_for_module(SmObjId, PiqYear, PiqSession)
            save_studyprograms_for_module(module_id, studyprograms)
            cnx.close()
            return jsonify(module_values), 200
        except mysql.connector.Error as err:
            return "Error: {}\nfor module {}".format(err, module_id), 409
    else:
        return 'No module found', 404

def save_studyprograms_for_module(module_id, studyprograms):
    print('deleting studyprogams', studyprograms, 'for module', module_id)
    cnx = mysql.connector.connect(**db_config)
    studyprogram_id = 0
    for sp in studyprograms:
        cursor = cnx.cursor()
        qry1 = "INSERT IGNORE INTO studyprogram (CgHighText, CgHighCategory) VALUES (%(CgHighText)s, %(CgHighCategory)s)"
        val1 = {
            'CgHighText':  sp['CgHighText'],
            'CgHighCategory': sp['CgHighCategory'],
        }
        cursor.execute(qry1, val1)
        studyprogram_id = cursor.lastrowid
        if studyprogram_id == 0:
            cursor.execute("SELECT id FROM studyprogram WHERE CgHighText = %(CgHighText)s AND CgHighCategory = %(CgHighCategory)s", val1)
            for row in cursor:
                print("studyprogram_id = cursor.lastrowid did not work", row)
                studyprogram_id = row[0]
        cnx.commit()

        qry2 = "INSERT IGNORE INTO module_studyprogram (module_id, studyprogram_id) VALUES (%(module_id)s, %(studyprogram_id)s)"
        val2 = {
            'module_id': module_id,
            'studyprogram_id': studyprogram_id,
        }
        print(val2)
        cursor.execute(qry2, val2)
        cnx.commit()
        cursor.close()

# delete studyprograms for module if there are no other modules with that SP.
def delete_studyprograms_for_module(module_id):
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor(buffered=True)
    # delete all studyprograms associated with that module...
    cursor.execute("SELECT studyprogram_id FROM module_studyprogram WHERE module_id = {};".format(module_id))
    studyprogram_ids=set()
    for row in cursor:
        studyprogram_ids.add(row[0])
    print('deleting studyprogams', studyprogram_ids, 'for module', module_id)
    for sp_id in studyprogram_ids:
        module_ids=set()
        cursor.execute("SELECT module_id FROM module_studyprogram WHERE studyprogram_id = {};".format(sp_id))
        for row in cursor:
            module_ids.add(row[0]) 
        # ... but only if they are not associated with any other module
        if len(module_ids) == 1:
            cursor.execute("DELETE FROM studyprogram WHERE id = {};".format(sp_id))
    cnx.commit()
    cursor.close()
    cnx.close()
            

@app.route('/modules/<int:module_id>', methods=['PUT'])
@cross_origin()
@require_appkey
def flag_module(module_id):
    whitelisted = int(request.args.get('whitelisted'))
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor(dictionary=True, buffered=True)
    # flag module as either black or whitelisted.
    try:
        cursor.execute("UPDATE module SET whitelisted = {} WHERE id = {}".format(whitelisted, module_id))

    except mysql.connector.Error as err:
        return "Error: {}".format(err), 409

    cnx.commit()
    cursor.close()
    cnx.close()
    if whitelisted:
        return 'Whitelisted Module with Id {}'.format(module_id), 200
    else:
        return 'Blacklisted Module with Id {}'.format(module_id), 200
    

# get blacklist
@app.route('/modules/blacklist', methods=['GET'])
@cross_origin()
def get_blacklist():
    return get_modules(whitelisted=0)

# remove module from database
@app.route('/modules/<int:module_id>', methods=['DELETE'])
@cross_origin()
@require_appkey
def remove_blacklist(module_id):
    # remove module
    try:
        cnx = mysql.connector.connect(**db_config)
        val = {'module_id': module_id}
        cursor = cnx.cursor(dictionary=True, buffered=True)
        qry = "DELETE FROM module WHERE id = %(module_id)s"
        cursor.execute(qry, val)
    except mysql.connector.Error as err:
        return "Error: {}".format(err), 500

    cnx.commit()
    cursor.close()
    cnx.close()
    return 'Deleted module', 200


# get all search terms
@app.route('/searchterms', methods=['GET'])
@cross_origin()
def get_searchterms():
    terms = []
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor(dictionary=True)
    qry = (
        "SELECT id, term FROM searchterm ORDER BY term ASC")
    cursor.execute(qry)
    for row in cursor.fetchall():
        for column, value in row.items():
            if type(value) is bytearray:
                row[column] = value.decode('utf-8')
        terms.append(row)
    return jsonify(terms)


# add search term
@app.route('/searchterms', methods=['POST'])
@cross_origin()
@require_appkey
def add_searchterm():
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor()
    data = request.form
    term = data['term']
    # term  =  'test'
    qry = "INSERT INTO searchterm (term) VALUES (%(term)s)"
    try:
        cursor.execute(qry, data)
        id = cursor.lastrowid
        cnx.commit()
        cnx.close()
        return jsonify({'id': id, 'term': term}), 200
    except mysql.connector.Error as err:
        cnx.close()
        return "Error: {}".format(err), 400


# remove search term
@app.route('/searchterms/<int:searchterm_id>', methods=['DELETE'])
@cross_origin()
@require_appkey
def remove_searchterm(searchterm_id):
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor()
    qry = "DELETE FROM searchterm WHERE id = %(searchterm_id)s"
    try:
        cursor.execute(qry, {'searchterm_id': searchterm_id})
        cnx.commit()
        cnx.close()
        return 'deleted', 200
    except mysql.connector.Error as err:
        cnx.close()
        return "Error: {}".format(err), 404


# get modules based on search terms, excluding those on white- and blacklist
@app.route('/search', methods=['GET'])
@cross_origin()
def search():
    start_time = time.perf_counter()
    # get searchterms
    terms = []
    id_not_currently_in_use = 999
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT term FROM searchterm")
        for row in cursor:
            terms.append(row['term'])
        cursor.close()
        cursor = cnx.cursor()
        cursor.execute("SELECT MAX(id) FROM module")
        id_not_currently_in_use = cursor.fetchone()[0] + 999

    except Exception as e:
        print('/search: not possible in dev', e)
        terms+=['Nachhaltigkeit', 'Sustainability']

    # get results for all searchterms
    modules = []
    for session in helpers.get_current_sessions():
        for searchterm in terms:
            rURI = "https://studentservices.uzh.ch/sap/opu/odata/uzh/vvz_data_srv/SmSearchSet?$skip=0&$top=20&$orderby=SmStext%20asc&$filter=substringof('{0}',Seark)%20and%20PiqYear%20eq%20'{1}'%20and%20PiqSession%20eq%20'{2}'&$inlinecount=allpages&$format=json".format(
                searchterm, str(session['year']).zfill(3), str(session['session']).zfill(3))

            r = requests.get(rURI)

            for module in r.json()['d']['results']:
                modules.append({
                    'SmObjId':    int(module['Objid']),
                    'title':          module['SmStext'],
                    'PiqYear':    int(module['PiqYear']),
                    'PiqSession': int(module['PiqSession']),
                    'searchterm': searchterm,
                })

    modules += json.loads(search_upwards().get_data())
    elapsed_time = time.perf_counter() - start_time
    # print("elapsed: getting modules", elapsed_time)
    
    # remove duplicates for mutable types
    keyfunc = lambda d: (d['SmObjId'], d['PiqYear'], d['PiqSession'])
    giter = groupby(sorted(modules, key=keyfunc), keyfunc)
    modules_no_duplicates = [next(g[1]) for g in giter]

    # flag elements that are already in database
    modules = check_which_saved(modules_no_duplicates)
    for i, mod in enumerate(modules_no_duplicates):
        # fake a database-like Id for easier identification in html
        mod['id'] = id_not_currently_in_use+i

    return jsonify(modules_no_duplicates)


def check_which_saved(modules):
    try:
        # flag elements that are already in database
        saved_modules = {}
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT SmObjId, PiqYear, PiqSession, whitelisted FROM module")
        for row in cursor:
            saved_modules[(row['SmObjId'], row['PiqYear'], row['PiqSession'])]=row['whitelisted']
        cursor.close()

        for mod in modules:
            module_key = (int(mod.get('SmObjId')), int(mod.get('PiqYear')), int(mod.get('PiqSession')))
            if module_key in saved_modules.keys():
                mod['whitelisted'] = saved_modules[module_key]
        

    except mysql.connector.errors.InterfaceError as e:
        print(e)
    return modules


"""
Request detail page for course object, add Module subobjects(dicts) as list to given course object 
"""
def find_modules_for_course(course):
    course['Modules'] = []
    rURI = models.Globals.URI_prefix+"EDetailsSet(EObjId='{}',PiqYear='{}',PiqSession='{}')?$expand=Rooms,Persons,Schedule,Schedule/Rooms,Schedule/Persons,Modules,Links&$format=json".format(
        course.get('EObjId'), course.get('PiqYear'), course.get('PiqSession')) #named params with **dict

    r = requests.get(rURI)

    # select each result of the 'Modules' subelement
    for module in r.json()['d']['Modules']['results']:
        course['Modules'].append({
            'SmObjId':    int(module['SmObjId']),
            'title':          module['SmText'],
            'PiqYear':    int(module['PiqYear']),
            'PiqSession': int(module['PiqSession']),
            'searchterm': course['searchterm'],
        })
    course['Modules'] = list({frozenset(item.items()) : item for item in course['Modules']}.values())
    return course['Modules']

"""
Request detail page for module object, add Studyprogrm subobjects(dicts) as list to given module obj
"""
def find_studyprograms_for_module(SmObjId, PiqYear, PiqSession):
    # SmDetailsSet(SmObjId='50934872',PiqYear='2018',PiqSession='004')?$expand=Partof%2cOrganizations%2cResponsible%2cEvents%2cEvents%2fPersons%2cOfferPeriods
    rURI = models.Globals.URI_prefix+"SmDetailsSet(SmObjId='{}',PiqYear='{}',PiqSession='{}')?$expand=Partof%2cOrganizations%2cResponsible%2cEvents%2cEvents%2fPersons%2cOfferPeriods&$format=json".format(
        SmObjId, PiqYear, PiqSession)
    module_values = {"Partof": []}
    r = requests.get(rURI)

    for studyprogram in r.json()['d']['Partof']['results']:
        module_values['Partof'].append({
            'CgHighText':     studyprogram['CgHighText'],
            'CgHighCategory': studyprogram['CgHighCategory'],
        })
    module_values['Partof'] = list({frozenset(item.items()) : item for item in module_values['Partof']}.values())
    return module_values['Partof']

"""
Wrapper function to be able to parallelize finding studyprograms for modules
"""
def wrap_execute_for_modules_in_course(course):
    with ThreadPoolExecutor(max_workers=10) as executor:
        return executor.map(find_studyprograms_for_module, course['Modules'])
    # return ThreadPool(len(course['Modules'])).imap_unordered(find_studyprograms_for_module, course['Modules'])

"""
Find course matches, then find containing modules, containing study programs
"""
@app.route('/search_upwards', methods=['GET'])
@cross_origin()
def search_upwards():
    start_time = time.perf_counter()
    # get searchterms
    terms = []
    try:
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT term FROM searchterm")
        for row in cursor:
            terms.append(row['term'])
    except Exception as e:
        print('not possible in dev', e)
        terms+=['Nachhaltigkeit', 'Sustainability']

    # get results for all searchterms
    courses = []
    modules = []
    for session in helpers.get_current_sessions():
        for searchterm in terms:
            rURI = models.Globals.URI_prefix+"ESearchSet?$skip=0&$top=20&$orderby=EStext%20asc&$filter=substringof('{0}',Seark)%20and%20PiqYear%20eq%20'{1}'%20and%20PiqSession%20eq%20'{2}'&$inlinecount=allpages&$format=json".format(
                searchterm, session['year'], session['session'])
            r = requests.get(rURI)
            for course in r.json()['d']['results']:
                courses.append({
                    'EObjId':     int(course['Objid']),
                    'EStext':         course['EStext'],
                    'PiqYear':    int(course['PiqYear']),
                    'PiqSession': int(course['PiqSession']),
                    'searchterm': searchterm,
                })
        # remove duplicates
        # courses = list({frozenset(item.items()) : item for item in courses}.values())

        
        # takes about 6 seconds for the two dev terms
        with ThreadPoolExecutor(max_workers=len(courses)+5) as executor:
            executor.map(find_modules_for_course, courses)
            # executor.map(wrap_execute_for_modules_in_course, courses)

        # takes >20 seconds for the two dev terms.        
        # for course in courses:
        #     find_modules_for_course(course)
            
        #     for module in course['Modules']:
        #         find_studyprograms_for_module(module)
            # print(course)
    for course in courses:
        modules += course['Modules']
    modules = list({frozenset(item.items()):item for item in modules}.values())
    elapsed_time = time.perf_counter() - start_time
    modules = check_which_saved(modules)
    # print("elapsed: getting courses->modules->studyprograms", elapsed_time)
    return jsonify(modules)


@app.route('/studyprograms', methods=['GET'])
@cross_origin()
def get_studyprograms():
    studyprograms=OrderedDict()
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor(dictionary=True)
    # Select all studyprograms for modules on the whitelist
    qry_p1 = """
    SELECT DISTINCT s.* 
        FROM studyprogram AS s 
        INNER JOIN module_studyprogram AS m_s 
        INNER JOIN module AS m 
    WHERE m.id = m_s.module_id AND s.id = m_s.studyprogram_id AND m.whitelisted = 1"""
    # If a specific semester is selected currently, only show for modules in that semester
    qry_p2 = " AND m.PiqYear = {} AND m.PiqSession = {}".format(request.args.get('PiqYear'), request.args.get('PiqSession')) if request.args.get('PiqSession', 'all_semesters') != "all_semesters" else ""
    cursor.execute(qry_p1+qry_p2+" ORDER BY s.CgHighText, s.CgHighCategory;")
    for row in cursor:
        for column, value in row.items():
            if type(value) is bytearray:
                row[column] = value.decode('utf-8')
        studyprograms[row['id']] = "{CgHighText}: {CgHighCategory}".format(**row)
    cnx.close()
    return app.response_class(
        response=json_builtin.dumps(studyprograms),
        status=200,
        mimetype='application/json'
    )

@app.route('/studyprograms_modules', methods=['GET'])
@cross_origin()
def get_studyprograms_modules():
    studyprogramid_moduleids = {}
    try: 
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT * FROM module_studyprogram AS m_s INNER JOIN module AS m WHERE m_s.module_id = m.id AND whitelisted = 1;")
        for row in cursor:
            for column, value in row.items():
                if type(value) is bytearray:
                    row[column] = value.decode('utf-8')
            if studyprogramid_moduleids.get(row['studyprogram_id']) is None:
                studyprogramid_moduleids[row['studyprogram_id']] = []
            studyprogramid_moduleids[row['studyprogram_id']].append(row['module_id'])
        cnx.close()
    except mysql.connector.Error as err:
        return "Error: {}".format(err), 500
    return jsonify(studyprogramid_moduleids)

@app.route('/modules_studyprogramstag', methods=['GET'])
@cross_origin()
def get_modules_studyprogramstag():
    moduleid_studyprogramids = {}
    try: 
        cnx = mysql.connector.connect(**db_config)
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT * FROM module_studyprogram;")
        for row in cursor:
            for column, value in row.items():
                if type(value) is bytearray:
                    row[column] = value.decode('utf-8')
            if moduleid_studyprogramids.get(row['module_id']) is None:
                moduleid_studyprogramids[row['module_id']] = ""
            moduleid_studyprogramids[row['module_id']] += str(row['studyprogram_id']) + " "
        cnx.close()
    except mysql.connector.Error as err:
        return "Error: {}".format(err), 500
    return jsonify(moduleid_studyprogramids)

if __name__ == "__main__":
    app.run()
