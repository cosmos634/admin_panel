from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
@app.route("/dashboard")
def dashboard():
	account = {
		"username": "cosm_0S",
		"name": "CosmOS",
		"followers": 9000000,
		"following": 0,
		"posts_count": 48
	}
	
	posts = [
		{
			"title": "Post #1",
			"views": "100000",
			"likes": "99977",
			"comments": "9276",
			"shares": "9275"
		},
		{
			"title": "Post #2",
			"views": "100000",
			"likes": "97007",
			"comments": "976",
			"shares": "975"
		}
		]
	
	return render_template("dashboard.html", account=account,  posts=posts)
	

@app.route("/automation")
def automation():
	return render_template("autmation.html")
	

@app.route("/settings")
def settings():
	return render_template("settings.html")


@app.route("/view-post")
def view_post():
	return render_template("view_post.html")
	
	
if __name__ == "__main__":
	app.run(debug=True)
