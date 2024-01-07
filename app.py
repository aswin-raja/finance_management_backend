from flask import Flask, request, jsonify, send_file
from db import create_connection, close_connection
from datetime import datetime
from flask_cors import CORS
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from io import BytesIO

app = Flask(__name__)
CORS(app)

# Create a database connection
db_connection = create_connection()


def generate_receipt(capture_id, off_type, date, time, amount, name):
    pdf_buffer = BytesIO()

    pdf_canvas = canvas.Canvas(pdf_buffer, pagesize=letter)

    # Set font and text color
    pdf_canvas.setFont("Helvetica-Bold", 16)

    # Add a header with a sky blue background
    pdf_canvas.setFillColorRGB(135/255, 206/255, 235/255)  # Sky Blue
    pdf_canvas.rect(0, 50, 612, 700)
    pdf_canvas.rect(0, 730, 612, 60, fill=True)
    pdf_canvas.setFillColor(colors.white)
    pdf_canvas.drawString(224, 765, "HOLY FAMILY CHURCH")
    pdf_canvas.drawString(250, 745, "Payment Receipt")


    # Define data for the table
    table_data = [
        ["ID", f"{capture_id}".upper()],
        ["Name", f"{name}".upper()],
        ["Off Type", f"{off_type}".upper()],
        ["Date", date],
        ["Time", time],
        ["Amount", f"${amount:.2f}"]
    ]

    # Create a table with complete width
    table = Table(table_data, colWidths=[200, 200], rowHeights=30)
    
    # Style the table
    style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.white),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                        ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
                         ('FONTSIZE', (0, 0), (-1, -1), 14),
                         ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),])


    # Apply the style to the table
    table.setStyle(style)

    # Draw the table on the canvas
    table.wrapOn(pdf_canvas, 400, 600)
    table.drawOn(pdf_canvas, 100, 480)
    # pdf_canvas.line(70, 190, 250, 190)  # Line above the signature
    # pdf_canvas.setFillColor(colors.black)
    # pdf_canvas.drawString(70, 150, "Signature:")
    
    img_path = './assets/sign.png'  # Replace with the actual path to your image
    pdf_canvas.drawImage(img_path, 355, 295, width=170, height=100)
    
    pdf_canvas.line(380, 290, 530, 290)  # Line above the treasurer information
    pdf_canvas.setFillColor(colors.black)
    pdf_canvas.drawString(380, 250, "Treasurer:")
    pdf_canvas.setFillColor(colors.black)
    pdf_canvas.drawString(460, 250, "John Doe") 

    # Add a line separator
    pdf_canvas.line(70, 160, 530, 160)
    pdf_canvas.setFillColor(colors.black)
    pdf_canvas.drawString(210, 120, "Thank you for your payment!")
    
    pdf_canvas.save()

    # Save the PDF file
    pdf_buffer.seek(0)

    # Return the PDF content as bytes
    return pdf_buffer.read()
    



@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Invalid request"}), 400

    username = data['username']
    password = data['password']

    # Use a cursor to execute queries
    cursor = db_connection.cursor(dictionary=True)

    try:
        # Execute a SELECT query to fetch user information
        query = "SELECT * FROM admin WHERE username = %s"
        cursor.execute(query, (username,))

        # Fetch the user data
        user = cursor.fetchone()

        if user and user['password'] == password:
            return jsonify({"message": "Login successful"}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    finally:

        cursor.close()


@app.route('/members', methods=['GET'])
def get_members():
    # Use a cursor to execute queries
    cursor = db_connection.cursor(dictionary=True)

    try:
        # Execute a SELECT query to fetch all members
        query = "SELECT members.*, JSON_ARRAYAGG(JSON_OBJECT('off_type', COALESCE(off_data.off_type, ''), 'amount', COALESCE(off_data.total_amount, 0))) AS off_types FROM members LEFT JOIN (SELECT id, off_type, SUM(amount) AS total_amount FROM off_data GROUP BY id, off_type) AS off_data ON members.id = off_data.id GROUP BY members.id;"

        cursor.execute(query)

        # Fetch all members' data
        members = cursor.fetchall()

        # Return the members as JSON
        return jsonify(members), 200

    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    finally:
        # Close the cursor
        cursor.close()


@app.route('/capture_off_data', methods=['POST'])
def capture_off_data():
    data = request.get_json()

    if not data or 'id' not in data or 'off_type' not in data or 'amount' not in data:
        return jsonify({"error": "Invalid request, missing required fields"}), 400

    # Extract data from the request
    capture_id = data['id']
    off_type = data['off_type']
    amount = float(data['amount']) if 'amount' in data else 0.0
    name= data['name']

    # Get the current date and time
    date = datetime.now().strftime('%Y-%m-%d')
    time = datetime.now().strftime('%H:%M:%S')

    # Use a cursor to execute queries
    cursor = db_connection.cursor()

    try:
        # Execute an INSERT query to store data in the off_data table
        query = "INSERT INTO off_data (id, off_type, date, time , amount) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, (capture_id, off_type, date, time,  amount))

        # Commit the transaction
        db_connection.commit()
        
        pdf_buffer = generate_receipt(capture_id, off_type, date, time, amount, name)

        # Send both JSON and PDF in the response
        return send_file(
            BytesIO(pdf_buffer),
            download_name=f'receipt_{capture_id}.pdf',
            as_attachment=True,
            mimetype='application/pdf'
        ), 200, {'message': 'Data captured successfully'}
        

    except Exception as e:
        # Rollback the transaction in case of an error
        db_connection.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    finally:
        # Close the cursor
        cursor.close()


@app.route('/generatemetrices', methods=['POST'])
def generate_metrics():
    try:
        # Get the 'month' parameter from the JSON request body
        data = request.get_json()
        if not data or 'month' not in data:
            return jsonify({'error': 'Invalid JSON request body'}), 400

        month_param = data['month']

        if month_param < 1 or month_param > 12:
            return jsonify({'error': 'Invalid month parameter'}), 400

        # Using a context manager for the cursor
        with db_connection.cursor() as cursor:
            # Your SQL query with parameterized input
            query = """
      SELECT
    off_type,
    MONTH(date) AS month,
    SUM(amount) AS total_amount
FROM
    off_data
WHERE
 month(date) = %s
GROUP BY
    off_type,
    MONTH(date);


            """

            cursor.execute(query, (month_param,))
            result = cursor.fetchall()
            json_data = {"month": month_param, "data": []}

            for row in result:
                off_type, total_amount = row[0], row[2]
                entry = {"off_type": off_type, "amount": total_amount}
                json_data["data"].append(entry)

        return jsonify(json_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
