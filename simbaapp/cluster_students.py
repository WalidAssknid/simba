import pandas as pd
import numpy as np
from typing import List, Dict, Any
from collections import Counter
import re

def extract_word_frequencies(messages_data: List[Dict[str, Any]], min_word_length: int = 3, max_words: int = 100) -> Dict:
    """
    Extract word frequencies from message data for word cloud visualization
    
    Parameters
    ----------
    messages_data : List[Dict]
        List of dictionaries containing message data
    min_word_length : int, optional
        Minimum length of words to include, by default 3
    max_words : int, optional
        Maximum number of words to return, by default 100
    
    Returns
    -------
    Dict
        Dictionary with word frequencies and student usage data
    """
    stopwords = set([
        'the', 'and', 'for', 'that', 'this', 'with', 'have', 'from', 'not', 'but', 'what', 'all', 'was', 'were',
        'when', 'where', 'who', 'will', 'more', 'are', 'they', 'than', 'been', 'would', 'could', 'should',
        'their', 'there', 'which', 'about', 'just', 'your', 'them', 'then', 'some', 'very', 'only', 'like',
        'also', 'into', 'back', 'after', 'over', 'these', 'those', 'know', 'because'
    ])
    
    word_by_student = {}
    word_counts = Counter()
    students = {}
    
    for msg in messages_data:
        user_id = msg.get('user_id')
        username = msg.get('username')
        
        if not user_id or not username or msg.get('role') != 'user':
            continue
            
        if user_id not in students:
            students[user_id] = {
                'user_id': user_id,
                'username': username
            }
            
        content = msg.get('content', '')
        if not content:
            continue
            
        words = re.sub(r'[^\w\s]', '', content.lower()).split()
        
        filtered_words = [
            word for word in words 
            if len(word) >= min_word_length and word not in stopwords and word.isalpha()
        ]
        
        word_counts.update(filtered_words)
        
        for word in set(filtered_words):  
            if word not in word_by_student:
                word_by_student[word] = set()
            word_by_student[word].add(user_id)
    
    word_data = []
    for word, count in word_counts.most_common(max_words):
        student_ids = list(word_by_student.get(word, set()))
        student_usernames = [students[student_id]['username'] for student_id in student_ids if student_id in students]
        
        word_data.append({
            'text': word,
            'value': count,
            'students': student_ids,
            'student_names': student_usernames
        })
    
    print(f"DEBUG: Extracted {len(word_data)} words from student messages")
    
    return {
        'words': word_data,
        'students': list(students.values())
    } 