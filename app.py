import os
import cv2
import numpy as np
from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageChops, ImageEnhance
# from pdf2image import convert_from_path 

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to perform Error Level Analysis (ELA)
def perform_ela(image_path, quality=90):
    try:
        original = Image.open(image_path).convert("RGB")
        temp_path = image_path.replace(".jpeg", "_temp.jpeg")
        original.save(temp_path, "JPEG", quality=quality)
        compressed = Image.open(temp_path)
        ela_image = ImageChops.difference(original, compressed)
        extrema = ela_image.getextrema()
        max_diff = max([ex[1] for ex in extrema])
        scale = 450.0 / max_diff if max_diff else 1
        ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
        ela_path = os.path.join(app.config['UPLOAD_FOLDER'], f'ela_{os.path.basename(image_path)}')
        ela_image.save(ela_path)
        return ela_path
    except Exception as e:
        print(f"Error in ELA: {e}")
        return None

# Function to calculate forgery percentage
def calculate_forgery_percentage(ela_image):
    """
    Calculate the percentage of potential forgery in an ELA image.
    """
    try:
        # Convert ELA image to grayscale
        ela_gray = cv2.cvtColor(np.array(ela_image), cv2.COLOR_RGB2GRAY)
        
        # Threshold to identify potential forged regions
        _, binary = cv2.threshold(ela_gray, 10, 255, cv2.THRESH_BINARY)
        
        # Calculate the percentage of white pixels (potential forgery)
        total_pixels = binary.size
        forged_pixels = np.count_nonzero(binary)
        forgery_percentage = (forged_pixels / total_pixels) * 100
        
        # Real percentage is the complement
        real_percentage = 100 - forgery_percentage
        
        return real_percentage, forgery_percentage
    except Exception as e:
        print(f"Error in calculating forgery percentage: {e}")
        return 95.0, 5.0  # Fallback values

# Function to highlight manipulated regions
def highlight_manipulations(image_path):
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Image not found or unable to read")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        highlighted = cv2.addWeighted(image, 3.0, edges_colored, 5.5, 0)
        highlighted_path = os.path.join(app.config['UPLOAD_FOLDER'], f'highlighted_{os.path.basename(image_path)}')
        cv2.imwrite(highlighted_path, highlighted)
        return highlighted_path
    except Exception as e:
        print(f"Error in highlighting manipulations: {e}")
        return None

# Function for MMFusion (Dummy Implementation)
def mmfusion_analysis(image_path):
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Image not found or unable to read")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mmfusion_image = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
        mmfusion_path = os.path.join(app.config['UPLOAD_FOLDER'], f'mmfusion_{os.path.basename(image_path)}')
        cv2.imwrite(mmfusion_path, mmfusion_image)
        return mmfusion_path
    except Exception as e:
        print(f"Error in MMFusion analysis: {e}")
        return None

# Function to handle PDF files
def process_pdf(pdf_path):
    try:
        # Convert PDF pages to images
        pages = convert_from_path(pdf_path, 300)
        results = []
        for i, page in enumerate(pages):
            # Save each page as an image
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], f'page_{i+1}.jpeg')
            page.save(image_path, 'JPEG')

            # Perform forgery detection on the image
            ela_path = perform_ela(image_path)
            highlighted_path = highlight_manipulations(image_path)
            mmfusion_path = mmfusion_analysis(image_path)

            # Calculate forgery percentages
            if ela_path:
                ela_image = Image.open(ela_path)
                real_percentage, forgery_percentage = calculate_forgery_percentage(ela_image)
            else:
                real_percentage, forgery_percentage = 95.0, 5.0  # Fallback values

            # Store results for each page
            results.append({
                'page_number': i+1,
                'original_image': f'uploads/{os.path.basename(image_path)}',
                'ela_image': f'uploads/{os.path.basename(ela_path)}' if ela_path else None,
                'highlighted_image': f'uploads/{os.path.basename(highlighted_path)}' if highlighted_path else None,
                'mmfusion_image': f'uploads/{os.path.basename(mmfusion_path)}' if mmfusion_path else None,
                'real_percentage': real_percentage,
                'forgery_percentage': forgery_percentage
            })
        return results
    except Exception as e:
        print(f"Error in processing PDF: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file uploaded"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Check if the file is a PDF
        if filename.lower().endswith('.pdf'):
            results = process_pdf(file_path)
            if results:
                return render_template('pdf_result.html', results=results)
            else:
                return "Error processing PDF"
        else:
            # Handle image files
            ela_path = perform_ela(file_path)
            highlighted_path = highlight_manipulations(file_path)
            mmfusion_path = mmfusion_analysis(file_path)
            if ela_path and highlighted_path and mmfusion_path:
                ela_image = Image.open(ela_path)
                real_percentage, forgery_percentage = calculate_forgery_percentage(ela_image)
                return render_template('result.html',
                                       original_image=f'uploads/{filename}',
                                       ela_image=f'uploads/{os.path.basename(ela_path)}',
                                       highlighted_image=f'uploads/{os.path.basename(highlighted_path)}',
                                       mmfusion_image=f'uploads/{os.path.basename(mmfusion_path)}',
                                       real_percentage=real_percentage,
                                       forgery_percentage=forgery_percentage)
            else:
                return "Error processing image"
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)