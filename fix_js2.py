import os

filepath = 'alumnos/templates/alumnos/sala_virtual.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Fix sendMessage function
old_func = '''    function sendMessage() {
        const input = document.getElementById('chat-input-text');
        const text = input.value.trim();
        if(!text) return;
        
        const msgContainer = document.getElementById('chat-messages');
        const now = new Date();
        const timeStr = now.getHours() + ':' + now.getMinutes().toString().padStart(2, '0');
        
        const msgHtml = 
            <div class="message">
                <div class="message-header">
                    <span class="sender">T</span>
                    <span class="time"></span>
                </div>
                <div class="text"></div>
            </div>
        ;
        msgContainer.innerHTML += msgHtml;
        msgContainer.scrollTop = msgContainer.scrollHeight;
        input.value = '';
    }'''

new_func = '''    function sendMessage() {
        const input = document.getElementById('chat-input-text');
        const text = input.value.trim();
        if(!text) return;
        
        const msgContainer = document.getElementById('chat-messages');
        const now = new Date();
        const timeStr = now.getHours() + ':' + now.getMinutes().toString().padStart(2, '0');
        
        const msgHtml = '<div class="message">' +
                '<div class="message-header">' +
                    '<span class="sender">Tú</span>' +
                    '<span class="time">' + timeStr + '</span>' +
                '</div>' +
                '<div class="text">' + text + '</div>' +
            '</div>';
        
        msgContainer.innerHTML += msgHtml;
        msgContainer.scrollTop = msgContainer.scrollHeight;
        input.value = '';
    }'''

if 'const msgHtml = \n            <div class="message">' in content:
    content = content.replace(old_func, new_func)
else:
    # Just replace it with regex to be safe
    content = re.sub(r'function sendMessage\(\) \{.*?(?=document\.getElementById\(\'chat-input-text\'\)\.addEventListener)', new_func + '\n\n    ', content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
