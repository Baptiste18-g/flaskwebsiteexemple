from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from werkzeug.utils import secure_filename

from flaskr.auth import login_required
from flaskr.db import get_db
from flask import send_file
import io
bp = Blueprint('blog', __name__)
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/')
def index():
    db = get_db()
    articles = db.execute(
        'SELECT p.id, title, body, created, author_id, username'
        ' FROM article p JOIN user u ON p.author_id = u.id'
        ' ORDER BY created DESC'
    ).fetchall()

    result = []
    for article in articles:

        article_dict = dict(article)
        article_id = article_dict['id']

        image = db.execute(
            'SELECT filename FROM image WHERE article_id = ?',
            (article_id,)
        ).fetchone()

        article_dict['image'] = image['filename'] if image else None
        result.append(article_dict)

    return render_template('blog/index.html', articles=result)



@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        image = request.files.get('image')
        error = None

        if not title:
            error = 'Title is required.'
        elif not body:
            error = 'Body is required.'
        elif image and not allowed_file(image.filename):
            error = 'Invalid image file format.'

        if error is not None:
            flash(error)
        else:

            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO article (title, body, author_id) VALUES (?, ?, ?)',
                (title, body, g.user['id'])
            )
            article_id = cursor.lastrowid
            db.commit()

            if image:

                filename = secure_filename(image.filename)
                image_data = image.read()

                cursor.execute(
                    'INSERT INTO image (article_id, filename, data) VALUES (?, ?, ?)',
                    (article_id, filename, image_data)
                )
                db.commit()

            return redirect(url_for('blog.index'))

    return render_template('blog/create.html')

def get_article(id, check_author=True):
    article = get_db().execute(
        'SELECT p.id, title, body, created, author_id, username'
        ' FROM article p JOIN user u ON p.author_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if article is None:
        abort(404, f"Article id {id} doesn't exist.")

    if check_author and article['author_id'] != g.user['id']:
        abort(403)

    return article

@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    article = get_article(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE article SET title = ?, body = ?'
                ' WHERE id = ?',
                (title, body, id)
            )
            db.commit()
            return redirect(url_for('blog.index'))

    return render_template('blog/update.html', article=article)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_article(id)
    db = get_db()
    db.execute('DELETE FROM article WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('blog.index'))
@bp.route('/image/<image_filename>')
def show_image(image_filename):
    db = get_db()
    image_data = db.execute(
        'SELECT data FROM image WHERE filename = ?',
        (image_filename,)
    ).fetchone()

    if image_data is None:
        abort(404, f"Image {image_filename} not found.")

    return send_file(io.BytesIO(image_data['data']), mimetype='image/jpeg')

@bp.route('/add_to_cart/<int:id>', methods=('POST',))
@login_required
def add_to_cart(id):
    db = get_db()

    # Vérifier si l'article est déjà dans le panier
    cart_item = db.execute(
        'SELECT quantity FROM cart WHERE user_id = ? AND article_id = ?',
        (g.user['id'], id)
    ).fetchone()

    if cart_item:
        # Si l'article existe déjà dans le panier, augmenter la quantité
        new_quantity = cart_item['quantity'] + 1
        db.execute(
            'UPDATE cart SET quantity = ? WHERE user_id = ? AND article_id = ?',
            (new_quantity, g.user['id'], id)
        )
    else:
        # Sinon, ajouter l'article au panier avec une quantité de 1
        db.execute(
            'INSERT INTO cart (user_id, article_id, quantity) VALUES (?, ?, ?)',
            (g.user['id'], id, 1)
        )

    db.commit()
    flash("Article ajouté au panier !")
    return redirect(url_for('blog.index'))

@bp.route('/cart')
@login_required
def cart():
    db = get_db()
    cart_items = db.execute(
        'SELECT a.id, a.title, a.body, c.quantity '
        'FROM cart c JOIN article a ON c.article_id = a.id '
        'WHERE c.user_id = ?',
        (g.user['id'],)
    ).fetchall()

    return render_template('blog/cart.html', cart_items=cart_items)

@bp.route('/remove_from_cart/<int:id>', methods=('POST',))
@login_required
def remove_from_cart(id):
    db = get_db()
    db.execute(
        'DELETE FROM cart WHERE user_id = ? AND article_id = ?',
        (g.user['id'], id)
    )
    db.commit()
    flash("Article retiré du panier !")
    return redirect(url_for('blog.cart'))

@bp.route('/checkout', methods=('POST',))
@login_required
def checkout():
    db = get_db()

    # Traiter la commande (par exemple, créer un enregistrement dans la table "orders")

    # Supprimer tous les articles du panier après la commande
    db.execute('DELETE FROM cart WHERE user_id = ?', (g.user['id'],))
    db.commit()

    flash("Commande réussie !")
    return redirect(url_for('blog.index'))

@bp.route('/update_quantity/<int:id>/<action>', methods=['GET', 'POST'])
@login_required
def update_quantity(id, action):
    # Récupérer l'article correspondant à l'id
    db = get_db()
    item = db.execute(
        'SELECT * FROM cart WHERE article_id = ? AND user_id = ?',
        (id, g.user['id'])
    ).fetchone()

    if item is None:
        abort(404, "Item not found in cart.")

    # Vérifier l'action (augmenter ou diminuer la quantité)
    if action == 'increase':
        new_quantity = item['quantity'] + 1
    elif action == 'decrease' and item['quantity'] > 1:
        new_quantity = item['quantity'] - 1
    else:
        flash("Quantity cannot be less than 1.")
        return redirect(url_for('blog.cart'))  # Retourner à la page d'index si l'action est invalide

    # Mettre à jour la quantité dans la base de données
    db.execute(
        'UPDATE cart SET quantity = ? WHERE article_id = ? AND user_id = ?',
        (new_quantity, id, g.user['id'])
    )
    db.commit()

    # Rediriger vers la page de panier après la mise à jour
    return redirect(url_for('blog.cart'))
