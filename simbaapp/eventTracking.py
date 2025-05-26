from .models import Event
import json

#Base function

def recordEvent(userId, verb, object, context, timestamp):
    event = Event.objects.create(
        user = userId,
        verb = verb,
        object = object,
        context = context,
        timestamp = timestamp
    )

    return event

# All users events

def accountCreated(userId,timestamp):
    event = recordEvent(userId, 0, 0, json.dumps({}), timestamp)
    return event

def loggedIn(userId,timestamp):
    event = recordEvent(userId, 2, 0, json.dumps({}), timestamp)
    return event

def loggedOut(userId,timestamp):
    event = recordEvent(userId, 3, 0, json.dumps({}), timestamp)
    return event

def openedChat(userId, threadId, timestamp):
    event = recordEvent(userId, 2, 3, json.dumps({"threadId" : threadId}), timestamp)
    return event

def closedChat(userId, threadId, timestamp):
    event = recordEvent(userId, 3, 3, json.dumps({"threadId" : threadId}), timestamp)
    return event

def sentMessage(userId, messageId, content, timestamp):
    """
    record when a message is sent

    :param userId: the user ID from the database
    :param messageId: the message ID from the database
    :param content: the message content of the sent message in string format
    :param timestamp: the timestamp from when the message was sent
    :return: the created event
    """
    event = recordEvent(userId, 0, 4, json.dumps({"messageId" : messageId, "messageContent" : content}), timestamp)
    return event

def joinedActivity(userId, activityId, timestamp):
    event = recordEvent(userId, 4, 2, json.dumps({"activityId" : activityId}), timestamp)
    return event

def joinedCourse(userId, courseId, timestamp):
    event = recordEvent(userId, 4, 1, json.dumps({"courseId" : courseId}), timestamp)
    return event

def openedCourse(userId, courseId, timestamp):
    event = recordEvent(userId, 2, 1, json.dumps({"courseId" : courseId}), timestamp)
    return event

def closedCourse(userId, courseId, timestamp):
    event = recordEvent(userId, 3, 1, json.dumps({"courseId" : courseId}), timestamp)
    return event

def modifiedProfile(userId, modification, timestamp):
    """
    record a profile modification

    :param userId: the user ID from the database
    :param modification: a dictionnary containing the modified elements and the nature of the modification
    :param timestamp: the timestamp from when the modification was done
    :return: the created event
    """
    event = recordEvent(userId, 5, 0, json.dumps({"modification" : modification}), timestamp)
    return event


# Teachers event
def createdActivity(userId, activityId, activityParameters, timestamp):
    """
    record an activity creation, only use if the creation was successful

    :param userId: the user ID from the database
    :param activityId: the activity ID from the database
    :param activityParameters: the original parameters of the activity as stored in the database, stored in a dictionary
    :param timestamp: the timestamp from when the activity was created
    :return: the created event
    """
    event = recordEvent(userId, 0, 2, json.dumps({"activityId" : activityId, "parameters" : activityParameters}), timestamp)
    return event

def modifiedActivity(userId, activityId, activityParameters, timestamp):
    """
    record an activity modification, only use if the modification was successful

    :param userId: the user ID from the database
    :param activityId: the activity ID from the database
    :param activityParameters: the new parameters of the activity as stored in the database, stored in a dictionary
    :param timestamp: the timestamp from when the activity was created
    :return: the created event
    """
    event = recordEvent(userId, 5, 2, json.dumps({"activityId" : activityId, "parameters" : activityParameters}), timestamp)
    return event

def deletedActivity(userId, activityId, timestamp):
    """
    record an activity deletion, only use if the deletion was successful

    :param userId: the user ID from the database
    :param activityId: the activity ID from the database
    :param timestamp: the timestamp from when the activity was deleted
    :return: the created event
    """
    event = recordEvent(userId, 1, 2, json.dumps({"activityId" : activityId}), timestamp)
    return event

def createdCourse(userId, courseId, courseParameters, timestamp):
    """
    record a course creation, only use if the creation was successful

    :param userId: the user ID from the database
    :param courseId: the course ID from the database
    :param courseParameters: the original parameters of the course as stored in the database, stored in a dictionary
    :param timestamp: the timestamp from when the course was created
    :return: the created event
    """
    event = recordEvent(userId, 0, 1, json.dumps({"courseId" : courseId, "parameters" : courseParameters}), timestamp)
    return event

def modifiedCourse(userId, courseId, courseParameters, timestamp):
    """
    record a course modification, only use if the creation was successful

    :param userId: the user ID from the database
    :param courseId: the course ID from the database
    :param courseParameters: the new parameters of the course as stored in the database, stored in a dictionary
    :param timestamp: the timestamp from when the course was modified
    :return: the created event
    """
    event = recordEvent(userId, 5, 1, json.dumps({"courseId" : courseId, "parameters" : courseParameters}), timestamp)
    return event

def deletedCourse(userId, courseId, timestamp):
    """
    record a course deletion, only use if the deletion was successful

    :param userId: the user ID from the database
    :param courseId: the course ID from the database
    :param timestamp: the timestamp from when the course was deleted
    :return: the created event
    """
    event = recordEvent(userId, 1, 1, json.dumps({"courseId" : courseId}), timestamp)
    return event

