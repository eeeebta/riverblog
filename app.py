import os
import re
import tarfile
from urllib.parse import quote_plus

import markdown as md
from flask import Flask, redirect, render_template, request, session, url_for, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.exceptions import InternalServerError, HTTPException
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from flask_session import Session
from helpers import login_required, admin_required

# !! Application set up !!
UPLOAD_FOLDER = "static/"
ALLOWED_EXTENSIONS = {"png", "jpeg", "jpg"}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Check for environment variables
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
if not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY is not set")

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Secret key
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

Session(app)

# SSL Mode is required to access the database securely
ssl_args = {"sslmode": "require"}

# Get the database environment variable, and generate the engine to connect to it, max of 50 connections
engine = create_engine(f"{os.getenv('DATABASE_URL')}", connect_args={"sslmode": "require"}, pool_size=15,
                       max_overflow=35)
db = scoped_session(sessionmaker(bind=engine))

# Create a category file based on existing categories in the database

# TODO Maybe think about adding another table where instead of getting this chunk of posts and deriving it,
#  i can basically just grab categories from there, and makes sure that text file is not necessary at any point
check_categories = db.execute("SELECT post_category FROM posts")

for a in range(30):
    print(check_categories)
temp_categories = ""

if check_categories is None:
    with open("categories.txt") as category_file:
        temp_categories = category_file.readlines()
else:
    check_categories = temp_categories

if len(temp_categories) < 1 or temp_categories is None:
    temp_categories = ["music_review", "cambridge_places"]

categories = []
for unformatted_category in temp_categories:
    categories.append(unformatted_category.strip("\n"))


# !! Main application !!
@app.route("/")
def home():
    # TODO Maybe here check if you're logged in as admin, and then give access to posting page in the header
    # Grab 5 posts from the music review category
    posts = db.execute("SELECT * FROM posts WHERE post_category='music_review' ORDER BY id DESC LIMIT 5").fetchall()

    return render_template("index.html", posts=posts)


@app.route("/about")
def about():
    return render_template("about.html")


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
    # return render_template("initial_blog_page.html", posts=posts, categories=categories)
    # For now just redirect to home
    return redirect(url_for("home"))

    # return render_template("initial_blog_page.html")


# Get all category posts
@app.route("/blog/<category>")
def get_all_cat_posts(category):
    # TODO create a template for this where posts can be listed by category/just this one
    # Check if a category exists within the defined list, and if it is check for it in the database, and verify
    # and after that return the post, if this is invalid/doesn't pass, then just return a 404 error
    # if category in categories:
    #     posts = db.execute("SELECT * FROM posts WHERE post_category = :category", {"category": category})
    #     if not posts:
    #         return web_error("Category not found", 404)
    #     else:
    #         return render_template("blog_category_listing.html", posts=posts)
    # return web_error("Category not found", 404)
    return "TODO"


# This is probably a bad approach: might be good to refactor/recode this to just return
# the file path/name over a post id, but it becomes a bit tricky without calling database
@app.route("/blog/<category>/<post_id>/<post_title>")
def get_post(category, post_id, post_title):
    # Get post from url
    path = f"templates/posts/{category}/{post_id}"

    # Check if the post exists
    does_path_exist = os.path.lexists(path)
    does_file_exist = os.path.exists(f"{path}/{post_title}.html")

    if not does_path_exist or not does_file_exist:
        return web_error("No post found", 404)

    # Remove template
    path = f"{path.replace('templates/', '')}/{post_title}.html"
    # # Check if it's only category, and if it is just display all the category posts
    # if post_id == "" or category == "":
    #     return ""
    # TODO render some sort of error if not found

    return render_template(path)


@app.route("/search", methods=["POST", "GET"])
def search():
    return "TODO"


# !! Creation tools/administration tools !!

@app.route("/admin", methods=["POST", "GET"])
def admin_page():
    # Log in for admin

    if session.get("user_id") is not None and session.get("superuser") is True:
        return redirect(url_for("create_post"))

    session.clear()

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # db.execute("UPDATE users SET password = :password WHERE username = :username", {"password": generate_password_hash(password)})

        user = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
        if not user:
            # return redirect(url_for("home"))
            return "does not exist"
        check_password = check_password_hash(user[2], password)

        if not user or not check_password:
            return "invalid password or username"
            # return redirect(url_for("home"))

        session["user_id"] = user[0]
        session["superuser"] = user[4]

        return redirect(url_for("create_post"))

    else:
        return render_template("login.html")


@app.route("/create", methods=["POST", "GET"])
@login_required
@admin_required
def create_post():
    # Check if the user trying to access this is an admin/has that cookie through the decorators
    if request.method == "POST":
        # TODO: Add an error page and catcher

        # Check if the album cover is attached
        if "file" not in request.files:
            # return "album cover not attached"
            return web_error("album cover not attached", 404)

        # Check if the file name is blank, and if so then return an error
        file = request.files["file"]
        if file.filename == "":
            #return "file name blank or album cover not attached"
            return web_error("file name blank or album cover not attached", 404)

        # Grab all of the form data
        title = request.form["postTitle"]
        author = request.form["postAuthor"]
        category = request.form["postCategory"].replace(" ", "_")
        content = request.form["postContent"]

        # Check validate that the file is allowed/exists and that all other fields exist/have been filled in
        if (file and allowed_file(file.filename)) and len(title) > 0 and len(author) > 0 and len(category) > 0 and \
                len(content) > 0:

            # Check if the post name already exists
            check_post = db.execute("SELECT * FROM posts WHERE post_title = :post_title",
                                    {"post_title": title}).fetchone()

            # If not, then return an error
            if check_post is not None:
                # return "Post name already exists"
                return web_error("post name already exists", 404)

            # Format the text for insertion into HTML files, or into the database
            original_title = title
            title = make_safe_title(title)
            content = convert_md_html(content)

            # Remove all HTML tags for the description
            content_sub_desc = content.strip('\n')
            post_desc = f"{re.sub('<[^>]*>', '', content_sub_desc)}..."[0:127]

            db.execute("""INSERT INTO posts (post_title, post_category, post_author, html_path, post_desc,
             post_original_title) VALUES (:post_title, :post_category, :post_author, :html_path,
              :post_desc, :p_og_title)""", {"post_title": title, "post_category": category, "post_author": author,
                                            "html_path": "replace", "post_desc": post_desc,
                                            "p_og_title": original_title})

            db.commit()

            # Grab the post from the database again to pass into generating a post file
            post = db.execute("SELECT * FROM posts WHERE post_title = :post_title", {"post_title": title}).fetchone()
            post_id = post[0]

            # Get the file extension
            ext = file.filename.split(".")[1]
            # TODO UPDATE THIS TO BE THE POST NUMBER/ID?

            # Change the file name to "album.<ext of file>"
            # TODO maybe rename this to cover?
            file.filename = f"album.{ext}"
            # Make sure that the filename is safe, though not really needed
            filename = secure_filename(file.filename)

            # The album/cover's name is the file name
            album_cover = filename

            # Generate the file -- also returning the html path where the post HTML file exists
            html_path = generate_post_file(post, content, original_title, album_cover)

            # Save the album/cover image to static under the respective category and post name
            file.save(f"static/posts/{category.replace(' ', '_')}/{post_id}/{file.filename}")

            # Update the HTML path since now it exists
            db.execute("UPDATE posts SET html_path = :html_path WHERE id = :post_id",
                       {"html_path": html_path, "post_id": post_id})
            db.commit()

            # Return the user to home, where they should now see the post under latest posts
            return redirect(url_for('home'))
        else:
            # TODO add javascript validation
            return "invalid post, you forgot some fields"
        # Upload the picture and add it to folder, under a folder that is named after post_id,
        # or just completely creating a new folder within static that is called post and within that create a folder
        # with the post_id, and have html file, and album_cover.whatever image
    else:
        # Return the template where the form is located.
        return render_template("create_post.html")


@app.route("/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_post():
    # Edit the post by re-opening up the
    return "TODO"


# In case for updates I need to return all posts (files get wiped), but probably a better
# solution is hosting on a personal server/provider instead of on a service
@app.route("/save_all_posts")
@login_required
@admin_required
def save_posts():
    # https://stackoverflow.com/questions/57945362/flask-send-a-zip-file-and-delete-it-afterwards
    # https://stackoverflow.com/questions/58422133/how-to-create-tar-gz-archive-in-python-tar-without-include-parent-directory
    # Write all of the posts to the post_data.tar.gz file and associated data, like album covers
    with tarfile.open("post_data" + ".tar.gz", mode="w:gz") as archive:
        archive.add("templates/posts", os.path.basename("templates/templates"))
        archive.add("static/posts", os.path.basename("static/static"))

    # Open the file so that I can stream it to the user
    with open("post_data.tar.gz", "rb") as f:
        data = f.readlines()

    # Remove the file
    os.remove("post_data.tar.gz")

    # Return the response of the data that is already loaded in memory as a gzip file
    return Response(data, headers={'Content-Type': 'application/gzip',
                                   'Content-Disposition': 'attachment; filename=post_data.tar.gz;'})


# !! Error handling !!

def errorhandler(e):
    # Handle errors

    # Check if the error is an HTTPException, and if it isn"t, then there was an internal server error
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return web_error(e.name, e.code)


def web_error(message, e_code=400):
    # Return the error + the webpage (default value of 400)
    return render_template("error.html", top=e_code, bottom=message), e_code


# !! Supplementary/processing function !!

# Convert markdown, which is what the posts will use for annotation, to html
def convert_md_html(md_text):
    # Get the markdown, then replace all paragraphs with divs due to those not being standard in the html files
    return md.markdown(md_text).replace("<p>", "<div>").replace("</p>", "</div>")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Take the post url, and make it usable for websites
def make_safe_title(title):
    # Return a clean title for the URL, but not for folder, it will be used to find folder
    return quote_plus(title.replace(" ", "-"))


# Create the HTML file using the post data that was just committed into the database, as well as taking
# data from the form that was submitted
def generate_post_file(post_data, post_content, org_post_title, album_cover):
    # Assign post elements to variables
    post_id = post_data[0]
    post_title = post_data[1]
    post_category = post_data[2]
    post_author = post_data[3]
    post_category_og = post_category

    # Replace the category's spaces with underscores to be url safe and readable
    post_category = post_category.replace(' ', '_')

    # TODO maybe a better idea to just create the paths at the start rather then checking each time

    if not os.path.lexists(f"templates/posts/{post_category}"):
        os.mkdir(f"templates/posts/{post_category}")

    # TODO Maybe replace this with a if statement like above
    if not os.path.lexists(f"templates/posts/{post_category}/{post_id}"):
        os.mkdir(f"templates/posts/{post_category}/{post_id}")
    else:
        return web_error("Post ID already exists")

    if not os.path.lexists(f"static/posts/{post_category}/{post_id}"):
        os.mkdir(f"static/posts/{post_category}/{post_id}")
    # try:
    #     # Make the directory where the post contents will be
    #     os.mkdir(f"template/posts/{post_category}/{post_id}")
    # except FileExistsError:
    #     # If there is already a folder of that, then there shouldn't be, and this should end here
    #     return None

    # Open up the base template and write to it the data that is relevant to the post
    with open("templates/post2.html", "r") as p_template, open(
            f"templates/posts/{post_category}/{post_id}/{post_title}.html", "a+") as p_complete:

        # Look through each line of the template and replace respective elements based on text
        for line in p_template:
            # TODO Might be a better way to do this -- maybe with a dictionary? {"REPLACE_<ITEM>": <item_variable>}
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
                                                        f"filename='posts/{post_category}/{post_id}/{album_cover}'")
                line = line.replace("REPLACE_ALBUM_COVER", ac_replace_str)

            if "REPLACE_POST_CONTENT" in line:
                line = line.replace("REPLACE_POST_CONTENT", convert_md_html(post_content))

            p_complete.write(line)

    html_path = f"templates/posts/{post_category}/{post_id}/{post_title}.html"
    # Return the HTML path, and image paths

    return html_path


# Assemble a path that will be used for locating the HTMl page
# TODO this might get removed
def fetch_post(category, post_id, post_title):
    # Something to note here that the "templates/" prefix MUST be removed if using render template
    assembled_path = f"templates/{category}/{post_id}/{post_title}.html"
    if os.path.exists(assembled_path):
        return assembled_path
    else:
        return None


def refresh_categories():
    # TODO this can be where the category function can be moved that was above at the top of the file
    return "TODO"


if __name__ == "__main__":
    app.run(threaded=True)
