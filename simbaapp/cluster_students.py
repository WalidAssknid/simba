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
        user_id = msg.get('user_id')
        username = msg.get('username')
        
        if not user_id or not username:
            continue
            
        if user_id not in user_data:
            user_data[user_id] = {
                'user_id': user_id,
                'username': username,
                'messages': [],
                'message_lengths': [],
                'activities': set(),
            }
        
        # Only include user messages in the analysis
        if msg.get('role') == 'user':
            content = msg.get('content', '')
            if content:  # Ensure content is not empty
                user_data[user_id]['messages'].append(content)
                user_data[user_id]['message_lengths'].append(len(content))
                activity_id = msg.get('activity_id')
                if activity_id:
                    user_data[user_id]['activities'].add(activity_id)
    
    # Print debug info
    print(f"DEBUG: Extracted data for {len(user_data)} users")
    for user_id, data in user_data.items():
        print(f"DEBUG: User {user_id} ({data['username']}) has {len(data['messages'])} messages")
    
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
    
    # If we have enough users but the extraction failed, add some dummy features
    if len(user_data) >= 2 and df.empty:
        print("DEBUG: Adding dummy features for users with no valid messages")
        for user_id, data in user_data.items():
            features.append({
                'user_id': user_id,
                'username': data['username'],
                'num_messages': 1,
                'total_length': 10,
                'avg_length': 10,
                'max_length': 10,
                'min_length': 10,
                'std_length': 0,
                'num_activities': 1,
                'vocab_size': 5,
                'lexical_diversity': 0.5
            })
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
        print(f"DEBUG: Not enough data ({len(user_features)} users) for {n_clusters} clusters")
        if len(user_features) <= 1:
            # Only one user, assign to cluster 0
            user_features['cluster'] = 0
            return user_features
        else:
            # Reduce the number of clusters to match data
            n_clusters = max(2, len(user_features) // 2)
            print(f"DEBUG: Reduced to {n_clusters} clusters")
    
    # Ensure all required features exist
    available_features = [f for f in model_features if f in user_features.columns]
    print(f"DEBUG: Available features for clustering: {available_features}")
    
    if not available_features:
        # No valid features, assign all to one cluster
        print("DEBUG: No valid features found for clustering")
        user_features['cluster'] = 0
        return user_features
    
    # If there are any missing values, fill them with means
    for feature in available_features:
        if user_features[feature].isnull().any():
            mean_value = user_features[feature].mean()
            user_features[feature] = user_features[feature].fillna(mean_value)
    
    # Normalize the features
    scaler = StandardScaler()
    try:
        normalized_features = scaler.fit_transform(user_features[available_features])
        print(f"DEBUG: Successfully normalized features")
    except Exception as e:
        print(f"ERROR in normalization: {str(e)}")
        # If normalization fails, assign sequential clusters
        user_features['cluster'] = [i % n_clusters for i in range(len(user_features))]
        return user_features
    
    # Apply K-means clustering
    try:
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(normalized_features)
        print(f"DEBUG: K-means clustering completed successfully")
    except Exception as e:
        print(f"ERROR in kmeans: {str(e)}")
        # If clustering fails, assign sequential clusters
        user_features['cluster'] = [i % n_clusters for i in range(len(user_features))]
        return user_features
    
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
    
    try:
        # Filter out non-numeric columns
        numeric_columns = clustered_data.select_dtypes(include=['number']).columns.tolist()
        numeric_features = [col for col in numeric_columns if col != 'cluster']
        
        print(f"DEBUG: Numeric features for clustering: {numeric_features}")
        
        if not numeric_features:
            # No numeric features available, return simple names
            for cluster_id in clustered_data['cluster'].unique():
                cluster_names[cluster_id] = f"Group {cluster_id + 1}"
            return cluster_names
            
        # Calculate cluster means
        cluster_means = clustered_data.groupby('cluster')[numeric_features].mean()
        
        # First pass: generate descriptive names
        descriptive_names = {}
        for cluster_id in clustered_data['cluster'].unique():
            # Skip if cluster is not in means (shouldn't happen)
            if cluster_id not in cluster_means.index:
                descriptive_names[cluster_id] = f"Group {cluster_id + 1}"
                continue
                
            # Get this cluster's means
            means = cluster_means.loc[cluster_id]
            
            primary_trait = ""
            
            # Prioritize vocabulary richness as primary characteristic
            if 'lexical_diversity' in means:
                all_clusters_lex_mean = cluster_means['lexical_diversity'].mean()
                if means['lexical_diversity'] > all_clusters_lex_mean * 1.2:
                    primary_trait = "Diverse Vocabulary"
                elif means['lexical_diversity'] < all_clusters_lex_mean * 0.8:
                    primary_trait = "Simple Vocabulary"
            
            # If no strong vocabulary trait, check message patterns
            if not primary_trait:
                has_freq_trait = False
                has_length_trait = False
                
                if 'num_messages' in means:
                    all_clusters_msg_mean = cluster_means['num_messages'].mean()
                    if means['num_messages'] > all_clusters_msg_mean * 1.2:
                        primary_trait = "Frequent Writers"
                        has_freq_trait = True
                    elif means['num_messages'] < all_clusters_msg_mean * 0.8:
                        primary_trait = "Infrequent Writers"
                        has_freq_trait = True
                
                if not has_freq_trait and 'avg_length' in means:
                    all_clusters_len_mean = cluster_means['avg_length'].mean()
                    if means['avg_length'] > all_clusters_len_mean * 1.2:
                        primary_trait = "Long Messages"
                        has_length_trait = True
                    elif means['avg_length'] < all_clusters_len_mean * 0.8:
                        primary_trait = "Short Messages"
                        has_length_trait = True
            
            # If still no primary trait, create a balanced descriptor
            if not primary_trait:
                primary_trait = "Balanced Communicators"
            
            # Store the primary trait
            descriptive_names[cluster_id] = primary_trait
        
        # Second pass: check for duplicates and make names unique
        used_names = set()
        name_counts = {}
        
        # Count occurrences of each name
        for name in descriptive_names.values():
            name_counts[name] = name_counts.get(name, 0) + 1
            
        # Process each cluster again to ensure unique names
        for cluster_id in sorted(clustered_data['cluster'].unique()):
            base_name = descriptive_names[cluster_id]
            
            # If this name appears multiple times, make it unique
            if name_counts.get(base_name, 0) > 1:
                # Get cluster size
                size = len(clustered_data[clustered_data['cluster'] == cluster_id])
                
                # Order clusters by some distinctive feature
                if 'avg_length' in cluster_means.columns:
                    distinction = "Higher Length" if cluster_means.loc[cluster_id, 'avg_length'] > cluster_means['avg_length'].median() else "Lower Length"
                elif 'num_messages' in cluster_means.columns:
                    distinction = "More Active" if cluster_means.loc[cluster_id, 'num_messages'] > cluster_means['num_messages'].median() else "Less Active"
                else:
                    # If no good distinction, use cluster ID
                    distinction = f"Group {cluster_id + 1}"
                
                # Create unique name
                unique_name = f"{base_name} ({distinction})"
                
                # Ensure uniqueness
                suffix = 1
                while unique_name in used_names:
                    suffix += 1
                    unique_name = f"{base_name} ({distinction} {suffix})"
                
                cluster_names[cluster_id] = unique_name
            else:
                cluster_names[cluster_id] = base_name
                
            used_names.add(cluster_names[cluster_id])
    
    except Exception as e:
        print(f"ERROR in get_cluster_names: {str(e)}")
        # If anything fails, use simple cluster names
        for cluster_id in clustered_data['cluster'].unique():
            cluster_names[cluster_id] = f"Group {cluster_id + 1}"
    
    return cluster_names 