import json
import re
import pymongo
# from random import randint, choice
from datetime import datetime
# from bson import BSON
from bson import json_util
from bson.objectid import ObjectId
# import isodate

class ClassDAO():

	def __init__(self, database):
		self.db = database
		self.studentdb = database.students
		self.coachdb = database.coaches
		self.classdb = database.classes

	def GetCoaches(self):
		co_recs = self.coachdb.find().sort("name",1)
		if co_recs is None:
			print("No coaches in database?")
			return None

		coaches = [{
				"_id"  : c['_id'],
				"name" : c['name'],
				"email" : c['email']
			} for c in co_recs]

		return coaches

	def AutocompleteStudent(self, name_start):
		first, last = None, None
		pieces = re.split("\W+", name_start)
		if len(pieces) > 1:
			first, last = pieces[0], pieces[1]
		elif len(pieces) == 1:
			first = pieces[0]
		else:
			return ""

		first_regex = re.compile("^" + first, re.IGNORECASE)
		last_regex = re.compile(("\w+" if last is None else "^"+last), re.IGNORECASE)

		matches = self.studentdb.aggregate([
			{
				"$match":{
					"firstname":first_regex,
					"lastname":last_regex
				}
			},
			{
				"$project":{
					"name":{
						"$concat":[
							"$firstname",
							" ",
							"$lastname"
						]
					}
				}
			}
		])

		students = [student['name'] for student in matches['result']]
		return json.dumps(students)

	def AddClassAttendance(self, classid, name, payment, method, ptype):		
		first, last = None, None
		pieces = re.split("\W+", name)
		if len(pieces) > 1:
			first, last = pieces[0], pieces[1]
		else:
			print("Name doesn't match pattern")
			return None

		stu_rec = self.studentdb.find_one({'firstname':first, 'lastname':last})
		if stu_rec is None:
			print("student does not exist")
			return

		att_rec = {"student" : stu_rec['_id']}
		if payment != "":
			att_rec.update({
				"payment" : {
					"amount" : int(payment),
					"method" : method,
					"purchased" : ptype
				}
			})
		elif ptype == "punched":
			att_rec.update({
				"payment" : {
					"amount" : 0,
					"method" : "punched",
					"purchased" : None
				}
			})

		self.classdb.update({
					'_id':ObjectId(classid)
				},
				{
					"$push":{
						"attendance":att_rec
					}
				}
			)

	def RemoveClassAttendance(self, class_id, student_id):
		classrec = self.classdb.find_one({"_id":ObjectId(class_id)})
		attendance = [att for att in classrec['attendance']]
		for i,att in enumerate(attendance):
			if att['student'] == ObjectId(student_id):
				del attendance[i]
				break

		classrec['attendance'] = attendance

		self.classdb.update({
				"_id":ObjectId(class_id)
			},
			{
				"$set":{
					"attendance":attendance
				}
			})

	def AddClass(self, coach, date, ctype):
		co_rec = self.coachdb.find_one({'name':coach})
		if co_rec is None:
			print("Coach name not in system")
			return
		
		new_class = {
			"date" : datetime.strptime(date, "%m/%d/%Y"),
			"coach" : co_rec['_id'],
			"type" : ctype,
			"attendance" : []
		}
		
		cla_rec = self.classdb.find_one({'date':new_class['date']})
		if cla_rec is not None:
			print("class already exists")
			return
				
		self.classdb.insert(new_class)
	
	def RemoveClass(self, class_id):
		self.classdb.remove({"_id":ObjectId(class_id)})

	def GetClass(self, classid):
		classrec = self.classdb.find_one({"_id":ObjectId(classid)})

		stud_ids = [rec["student"] for rec in classrec["attendance"]]
		dbstudents = self.studentdb.find({"_id":{"$in":stud_ids}})
		students = {student['_id']:student for student in dbstudents}

		coach = self.coachdb.find_one({"_id": classrec["coach"]})

		classdata = {
			"id" : classrec['_id'],
			"date": classrec['date'].strftime("%A, %B %d %Y"),
			"coach": coach["name"],
			"type": classrec["type"],
			"attendance": []
			# "notes": classrec["notes"]
		}

		for attrecord in classrec["attendance"]:
			student = students[attrecord["student"]]
			name = student["firstname"] + " " + student["lastname"]
			# bday = student["dob"].strftime("%A, %B %d %Y at %I:%M%p")
			age = int((datetime.now() - student["dob"]).days/365.2425)

			classrow = {
				"id" : student['_id'],
				"name" : name,
				"age" : age,
				"gender" : student['gender'],
				"purchased" : "",
				"purchasemethod" : ""
			}

			if "payment" in attrecord:
				if attrecord["payment"]["purchased"] is not None:
					classrow["purchased"] = "$" + str(attrecord["payment"]["amount"]) + " " + attrecord["payment"]["purchased"]
				else:
					classrow["purchased"] = ""
				classrow["purchasemethod"] = attrecord["payment"]["method"]
			classdata["attendance"].append(classrow)

		return classdata

	def GetClasses(self):
		dbclasses = self.classdb.find().sort("date",-1)
		dbcoaches = self.coachdb.find()

		coaches = dict()
		for coach in dbcoaches:
			coaches[coach['_id']] = coach['name']

		classtable = [{
				"id": classd['_id'],
				"coach": coaches[classd['coach']],
				"type" : classd["type"],
				"date": classd['date'].strftime("%A, %B %d %Y"),
				"attendance": len(classd["attendance"])
			} for classd in dbclasses]

		return classtable

	def EditStudent(self, name, dob, gender, email, emergencycontact, emergencyphone, student_id):
		first, last = None, None
		pieces = re.split("\W+", name)
		if len(pieces) > 1:
			first, last = pieces[0], pieces[1]
		else:
			print("Name doesn't match pattern")
			return None

		student = {
			"firstname" : first,
			"lastname" : last,
			"dob" : datetime.strptime(dob, "%m/%d/%Y"),
			"email" : email,
			"gender" : gender,
			"emergencycontact" : emergencycontact,
			"emergencyphone" : emergencyphone
		}

		self.studentdb.update({'_id':ObjectId(student_id)}, student)

	def AddStudent(self, name, dob, gender, email, emergencycontact, emergencyphone):
		first, last = None, None
		pieces = re.split("\W+", name)
		if len(pieces) > 1:
			first, last = pieces[0], pieces[1]
		else:
			print("Name doesn't match pattern")
			return None

		student = {
			"firstname" : first,
			"lastname" : last,
			"dob" : datetime.strptime(dob, "%m/%d/%Y"),
			"email" : email,
			"gender" : gender,
			"emergencycontact" : emergencycontact,
			"emergencyphone" : emergencyphone
		}

		stu_rec = self.studentdb.find_one({'firstname':first, 'lastname':last})
		if stu_rec is not None:
			print("Student already exists")
			return

		self.studentdb.insert(student)
		
	def GetStudents(self):
		dbstudents = self.studentdb.find({}).sort("lastname",1)

		studenttable = [{
				"id" : stu_rec['_id'],
				"name": stu_rec['firstname'] + " " + stu_rec['lastname'],
				"age" : int((datetime.now() - stu_rec["dob"]).days / 365.2425),
				"gender" : stu_rec["gender"],
				"email" : stu_rec["email"],
			} for stu_rec in dbstudents]

		return studenttable

	def GetStudent(self, student_id, edit=False):
		stu_rec = self.studentdb.find_one({'_id':ObjectId(student_id)})

		dob_format_string = ("%m/%d/%Y" if edit else "%A, %B %d %Y")
		student = {
			"id": stu_rec['_id'],
			"name": stu_rec['firstname'] + " " + stu_rec['lastname'],
			"dob" : stu_rec["dob"].strftime(dob_format_string),
			"gender" : stu_rec["gender"],
			"email" : stu_rec["email"],
			"emergencycontact" : stu_rec["emergencycontact"],
			"emergencyphone" : stu_rec["emergencyphone"]
		}

		return student

def j0(obj):return json.dumps(obj, sort_keys=True, indent=4, default=json_util.default)
def jprint(obj):print(j0(obj))
