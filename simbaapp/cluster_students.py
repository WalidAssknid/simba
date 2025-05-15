import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Any

def extract_features(messages_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Extract features from message data for clustering
    
    Parameters
    ----------
    messages_data : List[Dict]
        List of dictionaries containing message data
    
    Returns
    -------
    pd.DataFrame
        DataFrame with user features extracted from messages
    """
    # Group messages by user
    user_data = {}
    
    for msg in messages_data:
        user_id = msg['user_id']
        if user_id not in user_data:
            user_data[user_id] = {
                'user_id': user_id,
                'username': msg['username'],
                'messages': [],
                'message_lengths': [],
                'activities': set(),
            }
        
        if msg['role'] == 'user':
            user_data[user_id]['messages'].append(msg['content'])
            user_data[user_id]['message_lengths'].append(len(msg['content']))
            user_data[user_id]['activities'].add(msg['activity_id'])
    
    # Extract features
    features = []
    for user_id, data in user_data.items():
        if not data['messages']:  # Skip users with no messages
            continue
            
        # Calculate basic features
        num_messages = len(data['messages'])
        total_length = sum(data['message_lengths'])
        avg_length = total_length / num_messages if num_messages > 0 else 0
        max_length = max(data['message_lengths']) if data['message_lengths'] else 0
        min_length = min(data['message_lengths']) if data['message_lengths'] else 0
        std_length = np.std(data['message_lengths']) if len(data['message_lengths']) > 1 else 0
        num_activities = len(data['activities'])
        
        # Calculate vocabulary features
        all_text = ' '.join(data['messages'])
        words = all_text.lower().split()
        unique_words = set(words)
        vocab_size = len(unique_words)
        lexical_diversity = vocab_size / len(words) if words else 0
        
        # Add to features list
        features.append({
            'user_id': user_id,
            'username': data['username'],
            'num_messages': num_messages,
            'total_length': total_length,
            'avg_length': avg_length,
            'max_length': max_length,
            'min_length': min_length,
            'std_length': std_length,
            'num_activities': num_activities,
            'vocab_size': vocab_size,
            'lexical_diversity': lexical_diversity
        })
    
    # Convert to DataFrame
    df = pd.DataFrame(features)
    return df

def run_clustering(user_features: pd.DataFrame,
                 n_clusters: int = 3,
                 model_features: List[str] = None) -> pd.DataFrame:
    """
    Cluster the students based on their conversation features
    
    Parameters
    ----------
    user_features : pd.DataFrame
        The conversation features of the students
    n_clusters : int, optional
        The number of clusters to create, by default 3
    model_features : List[str], optional
        The features to use for clustering, by default None
        
    Returns
    -------
    pd.DataFrame
        The input dataframe with an additional column 'cluster' containing the cluster labels
    """
    if model_features is None:
        model_features = [
            'num_messages', 'avg_length', 'vocab_size', 
            'lexical_diversity', 'num_activities'
        ]
    
    # Check if we have enough data to cluster
    if len(user_features) < n_clusters:
        # Not enough data, assign all to one cluster
        user_features['cluster'] = 0
        return user_features
    
    # Ensure all required features exist
    available_features = [f for f in model_features if f in user_features.columns]
    if not available_features:
        # No valid features, assign all to one cluster
        user_features['cluster'] = 0
        return user_features
    
    # Normalize the features
    scaler = StandardScaler()
    normalized_features = scaler.fit_transform(user_features[available_features])
    
    # Apply K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    cluster_labels = kmeans.fit_predict(normalized_features)
    
    # Add cluster labels to the dataframe
    user_features['cluster'] = cluster_labels
    
    return user_features

def get_cluster_names(clustered_data: pd.DataFrame) -> Dict[int, str]:
    """
    Generate descriptive names for clusters based on their characteristics
    
    Parameters
    ----------
    clustered_data : pd.DataFrame
        DataFrame with cluster assignments and features
    
    Returns
    -------
    Dict[int, str]
        Dictionary mapping cluster IDs to descriptive names
    """
    cluster_names = {}
    
    # Calculate cluster means
    cluster_means = clustered_data.groupby('cluster').mean()
    
    for cluster_id in clustered_data['cluster'].unique():
        # Skip if cluster is not in means (shouldn't happen)
        if cluster_id not in cluster_means.index:
            cluster_names[cluster_id] = f"Cluster {cluster_id}"
            continue
            
        # Get this cluster's means
        means = cluster_means.loc[cluster_id]
        
        # Determine message frequency characteristic
        all_clusters_msg_mean = cluster_means['num_messages'].mean()
        if means['num_messages'] > all_clusters_msg_mean * 1.2:
            msg_freq = "Frequent"
        elif means['num_messages'] < all_clusters_msg_mean * 0.8:
            msg_freq = "Infrequent"
        else:
            msg_freq = "Average"
            
        # Determine message length characteristic
        all_clusters_len_mean = cluster_means['avg_length'].mean()
        if means['avg_length'] > all_clusters_len_mean * 1.2:
            msg_len = "Long"
        elif means['avg_length'] < all_clusters_len_mean * 0.8:
            msg_len = "Short"
        else:
            msg_len = "Average"
            
        # Determine vocabulary richness
        all_clusters_lex_mean = cluster_means['lexical_diversity'].mean()
        if means['lexical_diversity'] > all_clusters_lex_mean * 1.2:
            vocab = "Rich"
        elif means['lexical_diversity'] < all_clusters_lex_mean * 0.8:
            vocab = "Simple"
        else:
            vocab = "Average"
        
        # Create descriptive name
        cluster_names[cluster_id] = f"{msg_freq} {msg_len} {vocab}"
    
    return cluster_names 