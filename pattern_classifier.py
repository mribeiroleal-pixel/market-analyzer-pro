"""Pattern Classifier"""

class PatternClassifier:
    def __init__(self, model_path=None):
        self.model = None
        self.is_trained = False
    
    def load_model(self):
        return False
    
    def predict(self, cluster):
        return "NEUTRO", 0.5
    
    def train(self, X, y):
        return False
