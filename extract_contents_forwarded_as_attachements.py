import os
import mailparser
import re
from bs4 import BeautifulSoup
import html2text
import base64

def is_truly_invisible(tag):
    if not tag or not hasattr(tag, 'get'):
        return False, None
    
    try:
        style = str(tag.get('style', '')).lower().replace(' ', '')
        
        if 'display:none' in style:
            return True, 'display:none'
        if 'visibility:hidden' in style:
            return True, 'visibility:hidden'
        
        if 'width:0' in style and 'height:0' in style:
            return True, 'width:0_height:0'
        
        if 'font-size:0' in style:
            try:
                all_descendants = tag.find_all(style=True)
                for desc in all_descendants:
                    desc_style = str(desc.get('style', '')).lower()
                    if re.search(r'font-size:\s*[1-9]', desc_style):
                        return False, None
            except:
                pass
            return True, 'font-size:0'
        
        return False, None
    except:
        return False, None

def remove_invisible_and_extract_text(html_content):
    try:
        if not html_content:
            return ''
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove hidden tags
        hidden_tags = soup.find_all(attrs={'hidden': True})
        for tag in hidden_tags:
            if tag and hasattr(tag, 'decompose'):
                try:
                    tag.decompose()
                except:
                    pass
        
        # Remove invisible styled tags
        tags_with_style = soup.find_all(style=True)
        for tag in tags_with_style:
            try:
                is_invisible, method = is_truly_invisible(tag)
                if is_invisible:
                    tag.decompose()
            except:
                pass
        
        # Remove CSS hidden classes
        style_tags = soup.find_all('style')
        hidden_classes = {}
        
        for style_tag in style_tags:
            if not style_tag:
                continue
            
            try:
                style_content = style_tag.get_text()
            except:
                style_content = None
            
            if style_content:
                style_lower = style_content.lower()
                
                try:
                    matches = re.findall(r'\.([^\s{]+)\s*{[^}]*display\s*:\s*none', 
                                       style_lower, re.IGNORECASE)
                    for match in matches:
                        if match:
                            hidden_classes[match] = 'css_display:none'
                except:
                    pass
                
                try:
                    matches = re.findall(r'\.([^\s{]+)\s*{[^}]*visibility\s*:\s*hidden', 
                                       style_lower, re.IGNORECASE)
                    for match in matches:
                        if match:
                            hidden_classes[match] = 'css_visibility:hidden'
                except:
                    pass
        
        for class_name in hidden_classes.keys():
            if not class_name:
                continue
            
            try:
                for element in soup.find_all(class_=class_name):
                    if element:
                        element.decompose()
            except:
                pass
        
        # Convert to text
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.body_width = 0
        
        text = h.handle(str(soup))
        return text
        
    except Exception as e:
        return ''

def parse_eml_file(eml_path):
    try:
        with open(eml_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        header_section = content[:1000].lower()
        
        has_delivered_to = 'delivered-to:' in header_section
        has_received = 'received:' in header_section
        
        if not has_delivered_to and not has_received:
            try:
                with open(eml_path, 'rb') as f:
                    encoded_content = f.read()
                
                decoded_content = base64.b64decode(encoded_content)
                mail = mailparser.parse_from_bytes(decoded_content)
                return mail
                
            except:
                pass
        
        mail = mailparser.parse_from_file(eml_path)
        return mail
        
    except Exception as e:
        print(f"Error parsing eml: {e}")
        return None

def get_email_content(eml_path):
    try:
        mail = parse_eml_file(eml_path)
        
        if not mail:
            print("Failed to parse email")
            return None
        
        subject = mail.subject if mail.subject else ""
        
        body = ""
        
        if mail.text_html and len(mail.text_html) > 0:
            first_html = mail.text_html[0]
            if first_html:
                body = remove_invisible_and_extract_text(first_html)
        
        if not body and mail.body:
            body = mail.body
        
        if not body:
            body = ""
        
        email_content = f"Subject: {subject}\n\n{body}"
        return email_content
        
    except Exception as e:
        print(f"Error extracting content: {e}")
        return None

if __name__ == "__main__":
    eml_file = "path/to/your/email.eml"
    
    content = get_email_content(eml_file)
    
    if content:
        print("Email Content:")
        print("="*80)
        print(content)
    else:
        print("Failed to extract email content")
