import os
import re
from pprint import pprint

import markdown as md

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from urllib.parse import quote_plus

from helpers import login_required, admin_required

UPLOAD_FOLDER = "static/"
ALLOWED_EXTENSIONS = {"png", "jpeg", "jpg"}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Check for environment variables
if not os.getenv("DATABASE_URL"):
   raise RuntimeError("DATABASE_URL is not set")

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Secret key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

Session(app)

ssl_args = {"sslmode": "require"}
engine = create_engine(f"{os.getenv('DATABASE_URL')}", connect_args={"sslmode": "require"}, pool_size=15,
                       max_overflow=35)
db = scoped_session(sessionmaker(bind=engine))

categories = ["music review", "test_category1"]


@app.route("/")
def home():
    # Maybe here check if you're logged in as admin, and then give access to posting page
    posts = db.execute("SELECT * FROM posts WHERE post_category='music_review' ORDER BY id DESC LIMIT 5").fetchall()

    return render_template("index.html", posts=posts)


@app.route("/blog")
def blog():
    # Query all categories and grab like 5 articles with a "more..." button, or something
    # posts = {}
    # for category in categories:
    #     posts[category] = []
    #
    # for category in categories:
    #     returned_posts = db.execute("SELECT 5 FROM posts WHERE post_category=:category",
    #                                 {"category": category}).fetchall()
    #     posts[category].append(returned_posts)
    #
    #     print(posts)
    #     print(returned_posts)

    # print(posts)
    #return render_template("initial_blog_page.html", posts=posts, categories=categories)
    # For now just redirect to home
    return redirect(url_for("home"))

    # return render_template("initial_blog_page.html")


# Get all category posts
@app.route("/blog/<category>")
def get_all_cat_posts(category):
    # TODO create a template for this where posts can be listed by category/just this one
    # posts = db.execute("SELECT * FROM posts WHERE post_category = :category", {"category": category})
    return render_template("index.html")


# This is probably a bad approach: might be good to refactor/recode this to just return
# the file path/name over a post id
@app.route("/blog/<category>/<post_title>")
def get_post(category, post_title):
    # Query database for posts and then post id/whatever
    post = db.execute("SELECT * FROM posts WHERE post_title=:post_title AND post_category=:post_category",
                      {"post_title": post_title, "post_category": category}).fetchone()

    print(post)
    if not post:
        return "no post found"

    # # Check if it's only category, and if it is just display all the category posts
    # if post_id == "" or category == "":
    #     return ""
    # TODO render some sort of error if not found

    return render_template(post[4][10:])


@app.route("/admin", methods=["POST", "GET"])
def admin_page():
    # Log in for admin

    if session.get("user_id") is not None and session.get("superuser") is True:
        return redirect(url_for("create_post"))

    session.clear()

    if request.method == "POST":
        print("got")
        username = request.form["username"]
        password = request.form["password"]
        print(username)

        # db.execute("UPDATE users SET password = :password WHERE username = :username", {"password": generate_password_hash(password)})

        user = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
        if not user:
            print("DOES NOT EXIST")
            return redirect(url_for("home"))
        check_password = check_password_hash(user[2], password)

        if not user or not check_password:
            return redirect(url_for("home"))

        session["user_id"] = user[0]
        session["superuser"] = user[4]

        return redirect(url_for("create_post"))

    else:
        return render_template("login.html")


@app.route("/test")
def test():
    return ""


@app.route("/create", methods=["POST", "GET"])
@login_required
@admin_required
def create_post():
    # Check if the user trying to access this is an admin/has that cookie
    if request.method == "POST":
        # TODO: Add an error page and catcher
        if "file" not in request.files:
            print("first")
            return render_template("index.html")

        file = request.files["file"]
        if file.filename == "":
            print("second")
            return render_template("index.html")

        title = request.form["postTitle"]
        author = request.form["postAuthor"]
        category = request.form["postCategory"].replace(" ", "_")
        content = request.form["postContent"]

        if (file and allowed_file(file.filename)) and len(title) > 0 and len(author) > 0 and len(category) > 0 and \
                len(content) > 0:
            # DO title formatting quote-plus thing
            print("third")
            check_post = db.execute("SELECT * FROM posts WHERE post_title = :post_title",
                                    {"post_title": title}).fetchone()

            if check_post is not None:
                return "Post name already exists"

            original_title = title
            title = make_safe_title(title)
            content = convert_md_html(content)
            post_desc = f"{re.sub('<[^>]*>', '', content[0:127])}..."

            # Though this was a storage saving measure for the most part,

            db.execute("""INSERT INTO posts (post_title, post_category, post_author, html_path, post_desc,
             post_original_title) VALUES (:post_title, :post_category, :post_author, :html_path, :post_desc, :p_og_title)""",
                       {"post_title": title, "post_category": category, "post_author": author, "html_path": "replace",
                        "post_desc": post_desc, "p_og_title": original_title})

            db.commit()

            post = db.execute("SELECT * FROM posts WHERE post_title = :post_title", {"post_title": title}).fetchone()
            post_id = post[0]
            for a in range(3):
                print(post)
            html_path, image_path = generate_post_file(post, content, original_title)
            db.execute("UPDATE posts SET html_path = :html_path WHERE id = :post_id",
                       {"html_path": html_path, "post_id": post_id})
            db.commit()
            ext = file.filename.split(".")[1]
            # TODO UPDATE THIS TO BE THE POST NUMBER/ID?
            # TODO standardize the extension along all album covers -- convert all to PNG?
            file.filename = f"album.{ext}"
            filename = secure_filename(file.filename)
            # TODO Replace upload folder
            #file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            file.save(f"static/posts/{category.replace(' ', '_')}/{post_id}/{file.filename}")
            print("SAVED")
            return redirect(url_for('home', filename=filename))
        else:
            # TODO add javascript validation
            return "invalid post, you forgot some fields"
        # Upload the picture and add it to folder, under a folder that is named after post_id,
        # or just completely creating a new folder within static that is called post and within that create a folder
        # with the post_id, and have html file, and album_cover.whatever image
    else:
        return render_template("create_post.html")


# Convert markdown, which is what the posts will use for annotation, to html
def convert_md_html(md_text):
    # Get the markdown, then replace all paragraphs with divs due to those not being standard in my html files
    return md.markdown(md_text).replace("<p>", "<div>").replace("</p>", "</div>")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Take the post url, and make it usable for websites
def make_safe_title(title):
    # Return a clean title for the URL, but not for folder, it will be used to find folder
    return quote_plus(title.replace(" ", "-"))


def generate_post_file(post_data, post_content, org_post_title):
    # post_data = {"title", "author, basically everything from table"}
    post_id = post_data[0]

    # Post title should be prepared already
    post_title = post_data[1]
    post_category = post_data[2]
    post_author = post_data[3]
    post_category_og = post_category

    post_category = post_category.replace(' ', '_')

    for a in range(30):
        print(os.path.lexists(f"templates/posts/{post_category}"))

    # TODO maybe a better idea to just create the paths at the start rather then checking each time

    if not os.path.lexists(f"templates/posts/{post_category}"):
        os.mkdir(f"templates/posts/{post_category}")

    # TODO Maybe replace this with a if statement like above
    if not os.path.lexists(f"templates/posts/{post_category}/{post_id}"):
        os.mkdir(f"templates/posts/{post_category}/{post_id}")
    else:
        return "Already exists"

    if not os.path.lexists(f"static/posts/{post_category}/{post_id}"):
        os.mkdir(f"static/posts/{post_category}/{post_id}")
    # try:
    #     # Make the directory where the post contents will be
    #     os.mkdir(f"template/posts/{post_category}/{post_id}")
    # except FileExistsError:
    #     # If there is already a folder of that, then there shouldn't be, and this should end here
    #     return None

    with open("templates/post2.html", "r") as p_template, open(f"templates/posts/{post_category}/{post_id}/{post_title}.html", "a+") as p_complete:
        for line in p_template:
            # TODO Might be a better way to do this
            if "REPLACE_POST_TITLE" in line:
                line = line.replace("REPLACE_POST_TITLE", org_post_title)

            if "REPLACE_CATEGORY" in line:
                line = line.replace("REPLACE_CATEGORY", post_category_og)

            if "REPLACE_AUTHOR" in line:
                line = line.replace("REPLACE_AUTHOR", post_author)

            # TODO replace album cover with just cover because it makes more sense in the context outside of music
            if "REPLACE_ALBUM_COVER" in line:
                ac_replace_str = "{{ url_for('static', filename='') }}"
                ac_replace_str = ac_replace_str.replace("filename=''",
                                                        f"filename='posts/{post_category}/{post_id}/album.jpeg'")
                line = line.replace("REPLACE_ALBUM_COVER", ac_replace_str)
                image_path = ac_replace_str

            if "REPLACE_POST_CONTENT" in line:
                line = line.replace("REPLACE_POST_CONTENT", convert_md_html(post_content))

            p_complete.write(line)

    html_path = f"templates/posts/{post_category}/{post_id}/{post_title}.html"
    # Return the HTML path, and image paths

    return html_path, image_path


def fetch_post(category, post_id, post_title):
    assembled_path = f"templates/{category}/{post_id}/{post_title}.html"
    if os.path.exists(assembled_path):
        return assembled_path
    else:
        return None


if __name__ == "__main__":
    app.run(threaded=True)
