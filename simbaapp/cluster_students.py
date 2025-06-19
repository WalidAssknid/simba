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

def cluster_students(messages_data: List[Dict[str, Any]], n_clusters: int = 3) -> Dict:
    """
    Cluster students based on their message patterns and extract features for visualization
    
    Parameters
    ----------
    messages_data : List[Dict]
        List of dictionaries containing message data
    n_clusters : int, optional
        Number of clusters to create, by default 3
    
    Returns
    -------
    Dict
        Dictionary with clusters and features data
    """
    
    student_data = {}
    for msg in messages_data:
        user_id = msg.get('user_id')
        username = msg.get('username')
        
        if not user_id or not username or msg.get('role') != 'user':
            continue
            
        if user_id not in student_data:
            student_data[user_id] = {
                'user_id': user_id,
                'username': username,
                'messages': [],
                'total_chars': 0,
                'message_count': 0
            }
        
        content = msg.get('content', '')
        if content:
            student_data[user_id]['messages'].append(content)
            student_data[user_id]['total_chars'] += len(content)
            student_data[user_id]['message_count'] += 1
    
    if len(student_data) < 2:
        features = []
        for user_id, data in student_data.items():
            if data['message_count'] > 0:
                avg_length = data['total_chars'] / data['message_count']
                vocab_size = len(set(' '.join(data['messages']).lower().split()))
                lexical_diversity = vocab_size / data['message_count'] if data['message_count'] > 0 else 0
                
                features.append({
                    'user_id': user_id,
                    'username': data['username'],
                    'num_messages': data['message_count'],
                    'avg_length': avg_length,
                    'vocab_size': vocab_size,
                    'lexical_diversity': lexical_diversity,
                    'cluster': 0
                })
        
        return {
            'clusters': [{
                'id': 0,
                'name': 'All Students',
                'size': len(features),
                'users': [{'username': f['username']} for f in features]
            }] if features else [],
            'features': features
        }
    
    features = []
    feature_matrix = []
    student_list = []
    
    for user_id, data in student_data.items():
        if data['message_count'] == 0:
            continue
            
        avg_length = data['total_chars'] / data['message_count']
        
        all_text = ' '.join(data['messages']).lower()
        words = re.sub(r'[^\w\s]', '', all_text).split()
        vocab_size = len(set(words))
        lexical_diversity = vocab_size / data['message_count'] if data['message_count'] > 0 else 0
        
        feature_dict = {
            'user_id': user_id,
            'username': data['username'],
            'num_messages': data['message_count'],
            'avg_length': avg_length,
            'vocab_size': vocab_size,
            'lexical_diversity': lexical_diversity
        }
        
        features.append(feature_dict)
        feature_matrix.append([
            data['message_count'],
            avg_length,
            vocab_size,
            lexical_diversity
        ])
        student_list.append(data)
    
    if len(features) < 2:
        return {
            'clusters': [],
            'features': [],
            'error': f"Need at least 2 students with messages for clustering. Found {len(features)}."
        }
    
    clusters = []
    cluster_assignments = []
    
    num_messages_values = [f['num_messages'] for f in features]
    avg_length_values = [f['avg_length'] for f in features]
    
    num_messages_median = np.median(num_messages_values)
    avg_length_median = np.median(avg_length_values)
    
    for i, feature_dict in enumerate(features):
        if feature_dict['num_messages'] >= num_messages_median and feature_dict['avg_length'] >= avg_length_median:
            cluster_id = 0
            cluster_name = "Frequent Writers (Long Messages)"
        elif feature_dict['num_messages'] >= num_messages_median and feature_dict['avg_length'] < avg_length_median:
            cluster_id = 1
            cluster_name = "Frequent Writers (Short Messages)"
        else:
            cluster_id = 2
            cluster_name = "Infrequent Writers"
        
        cluster_assignments.append(cluster_id)
        feature_dict['cluster'] = cluster_id
    
    cluster_names = [
        "Frequent Writers (Long Messages)",
        "Frequent Writers (Short Messages)", 
        "Infrequent Writers"
    ]
    
    for cluster_id in range(3):
        cluster_students = [f for f in features if f['cluster'] == cluster_id]
        if cluster_students:
            clusters.append({
                'id': cluster_id,
                'name': cluster_names[cluster_id],
                'size': len(cluster_students),
                'users': [{'username': s['username']} for s in cluster_students]
            })
    
    print(f"DEBUG: Created {len(clusters)} clusters with {len(features)} students")
    
    return {
        'clusters': clusters,
        'features': features
    } 