import pymongo    
from classDA import ClassDAO
from flask import Flask, url_for, redirect, render_template, request, session
from flask_oauth import OAuth
import json
import os

app = Flask(__name__)
app.debug = True

path = os.environ['OPENSHIFT_REPO_DIR']
with open(path + "wsgi/authinfo.json") as jauth:
    authinfo = json.load(jauth)

app.secret_key = authinfo["secret_key"]
oauth = OAuth()
google = oauth.remote_app('google',
                        base_url='https://www.google.com/accounts/',
                        authorize_url='https://accounts.google.com/o/oauth2/auth',
                        request_token_url=None,
                        request_token_params={
                            'scope': 'https://www.googleapis.com/auth/userinfo.email',
                            'response_type': 'code'
                        },
                        access_token_url='https://accounts.google.com/o/oauth2/token',
                        access_token_method='POST',
                        access_token_params={'grant_type': 'authorization_code'},
                        consumer_key=authinfo["consumer_key"],
                        consumer_secret=authinfo["consumer_secret"])

mongostr = "mongodb://{}:{}@{}:{}".format(
        os.environ['OPENSHIFT_MONGODB_DB_USERNAME'],
        os.environ['OPENSHIFT_MONGODB_DB_PASSWORD'],
        os.environ['OPENSHIFT_MONGODB_DB_HOST'],
        os.environ['OPENSHIFT_MONGODB_DB_PORT'],
    )

con = pymongo.MongoClient(mongostr)
dao = ClassDAO(con.pkclass)
coaches = dao.GetCoaches()
valid_emails = [c['email'] for c in coaches]

@app.route('/')
def index():
    access_token = session.get('access_token')
    if access_token is None:
        return redirect(url_for('login'))

    access_token = access_token[0]
    from urllib2 import Request, urlopen, URLError

    headers = {'Authorization': 'OAuth '+access_token}
    req = Request('https://www.googleapis.com/oauth2/v1/userinfo',
                  None, headers)
    try:
        user_info = json.load(urlopen(req))
    except URLError as e:
        if e.code == 401:
            # Unauthorized - bad token
            session.pop('access_token', None)
            return redirect(url_for('login'))
        return "Error authorizing: " + json.dumps(user_info)

    session["email"] = user_info.get("email")
    return redirect(url_for("classes_page",))

@app.route('/login')
def login():
    callback=url_for('authorized', _external=True)
    return google.authorize(callback=callback)

@app.route("/oauth2callback")
@google.authorized_handler
def authorized(resp):
    access_token = resp['access_token']
    session['access_token'] = access_token, ''
    return redirect(url_for('index'))

@google.tokengetter
def get_access_token():
    return session.get('access_token')

@app.route('/students', methods=['POST', 'GET'])
def students_page():
    if request.method == 'POST':
        # print(request.form)
        name = request.form.get('name')
        dob = request.form.get('dob')
        emergencyphone = request.form.get('emergencyphone')
        emergencycontact = request.form.get('emergencycontact')
        gender = request.form.get('gender')
        email = request.form.get('email')
        dao.AddStudent(name, dob, gender, email, emergencycontact, emergencyphone)
    return render_template('students.html', students = dao.GetStudents())

@app.route('/student_autocomplete')
def student_autocomplete():
    term = request.args.get("term")
    return dao.AutocompleteStudent(term)

@app.route('/student/<student_id>', methods=['POST', 'GET'])
def student_page(student_id):
    if request.method == 'POST':
        print(request.form)
        name = request.form.get('name')
        dob = request.form.get('dob')
        emergencyphone = request.form.get('emergencyphone')
        emergencycontact = request.form.get('emergencycontact')
        gender = request.form.get('gender')
        email = request.form.get('email')
        dao.EditStudent(name, dob, gender, email, emergencycontact, emergencyphone, student_id)
        return render_template('students.html', students = dao.GetStudents())
    return render_template('student.html', student = dao.GetStudent(student_id))

@app.route('/edit_student/<student_id>', methods=['POST', 'GET'])
def edit_student(student_id):
    return render_template('edit_student.html', student = dao.GetStudent(student_id, edit=True))

@app.route('/classes', methods=['POST', 'GET'])
def classes_page():
    if request.method == 'POST':
        coach = request.form.get('coach')
        date = request.form.get('date')
        ctype = request.form.get('type')
        dao.AddClass(coach, date, ctype)
    return render_template('classes.html', classes = dao.GetClasses(), coaches = dao.GetCoaches())

@app.route('/remove_class/<class_id>', methods=['POST'])
def remove_class(class_id):
    dao.RemoveClass(class_id)
    return redirect(url_for('classes_page', class_id=class_id))

@app.route('/class/<class_id>', methods=['POST', 'GET'])
def class_page(class_id):
    if request.method == 'POST':
        name = request.form.get('name')
        payment = request.form.get('payment')
        method = request.form.get('method')
        ptype = request.form.get('type')
        dao.AddClassAttendance(class_id, name, payment, method, ptype)
    return render_template('class.html', classrec = dao.GetClass(class_id))

@app.route('/remove_attendance/<class_id>', methods=['POST'])
def remove_attendance(class_id):
    student_id = request.form.get('student_id')
    dao.RemoveClassAttendance(class_id, student_id)
    return redirect(url_for('class_page', class_id=class_id))

@app.before_request
def check_auth():
    email = session.get("email")
    if valid_emails and email not in valid_emails:
        redirect(url_for('login'))

if __name__ == "__main__":
    app.run()

