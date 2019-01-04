import tensorflow as tf
from tensorflow.python import keras
from tensorflow.python.keras.layers import (
    Dense, Concatenate, Reshape, Activation, LSTM, Lambda)
from tensorflow.python.keras.initializers import RandomUniform
from .layer_norm import LayerNorm
from .noisy_dense import NoisyDense
from .actor_networks_lstm import dense_block


# def dense_block(input_layer, hiddens, activation="relu",
#                 layer_norm=False, noisy_layer=False):
#     out = input_layer
#     for num_units in hiddens:
#         if noisy_layer:
#             out = NoisyDense(num_units, None)(out)
#         else:
#             out = Dense(num_units, None)(out)
#         if layer_norm:
#             out = LayerNorm()(out)
#         out = Activation(activation)(out)
#     return out


class CriticNetwork:

    def __init__(self, state_shape, action_size,
                 embedding_layers=[256, 128, 64, 32],
                 embedding_activations=["relu", "relu", "relu", "relu"],
                 lstm_layers=[64, 32],
                 lstm_activations=["relu", "relu"],
                 output_layers=[256, 128, 64, 32],
                 output_layers_activations=["relu", "relu", "relu", "relu"],
                 output_activation="tanh",
                 num_atoms=1,
                 v=(-10., 10.),
                 layer_norm=False, noisy_layer=False,
                 scope=None):

        self.state_shape = state_shape
        self.action_size = action_size
        self.embedding_layers = embedding_layers
        self.embedding_activations = embedding_activations
        self.lstm_layers = lstm_layers
        self.lstm_activations = lstm_activations
        self.output_layers = output_layers
        self.output_layers_activations = output_layers_activations
        self.output_activation = output_activation
        # self.act_insert_block = action_insert_block
        self.num_atoms = num_atoms
        self.v = v
        self.layer_norm = layer_norm
        self.noisy_layer = noisy_layer
        self.scope = scope or "CriticNetwork"
        self.model = self.build_model()

    def build_model(self):
        print('--- critic')
        with tf.variable_scope(self.scope):
            input_state = keras.layers.Input(
                shape=self.state_shape, name="state_input")
            input_action = keras.layers.Input(
                shape=(self.action_size, ), name="action_input")

            model_inputs = [input_state, input_action]

            out = input_state
            for layer_size, activation in zip(self.embedding_layers, self.embedding_activations):
                out = dense_block(
                    out,
                    layer_size,
                    activation,
                    self.layer_norm,
                    self.noisy_layer
                )
            print('--- dense {}'.format(out))
            
            # def repeat(layer):
            #     return tf.keras.backend.repeat(
            #         layer,
            #         self.state_shape[0]
            #     )
            # 
            # out = Concatenate(axis=2)([
            #     out,
            #     Lambda(repeat)(input_action)
            # ])
            # print('--- concat {}'.format(out))

            for layer_size, activation in zip(self.lstm_layers[:-1], self.lstm_activations[:-1]):
                out = LSTM(layer_size, activation=activation, return_sequences=True)(out)
            out = LSTM(
                units=self.lstm_layers[-1],
                activation=self.lstm_activations[-1]
            )(out)
            print('--- out lstm {}'.format(out))

            out = Concatenate(axis=1)([
                out,
                input_action
            ])
            print('--- concat {}'.format(out))

            for layer_size, activation in zip(self.output_layers, self.output_layers_activations):
                out = dense_block(
                    out,
                    layer_size,
                    activation,
                    self.layer_norm,
                    self.noisy_layer
                )
            print('--- output layers {}'.format(out))
            
            out = Dense(
                self.num_atoms,
                self.output_activation,
                kernel_initializer=RandomUniform(-3e-3, 3e-3),
                bias_initializer=RandomUniform(-3e-3, 3e-3)
            )(out)

            print('--- out {}'.format(out))

            model = keras.models.Model(inputs=model_inputs, outputs=out)
        return model

    def get_input_size(self, shape):
        if len(shape) == 1:
            return shape[0]
        elif len(shape) == 2:
            return shape[0] * shape[1]

    def __call__(self, inputs):
        # if self.act_insert_block == -1:
        #     state_input = inputs[0]
        #     model_input = state_input
        # else:
        state_input = inputs[0][0]
        action_input = inputs[1]
        model_input = [state_input, action_input]
        return self.model(model_input)

    def variables(self):
        return self.model.trainable_weights

    def copy(self, scope=None):
        """copy network architecture"""
        scope = scope or self.scope + "_copy"
        with tf.variable_scope(scope):
            return CriticNetwork(
                state_shape=self.state_shape,
                action_size=self.action_size,
                embedding_layers=self.embedding_layers,
                embedding_activations=self.embedding_activations,
                output_layers=self.output_layers,
                output_layers_activations=self.output_layers_activations,
                lstm_layers=self.lstm_layers,
                lstm_activations=self.lstm_activations,
                # action_insert_block=self.act_insert_block,
                num_atoms=self.num_atoms,
                v=self.v,
                layer_norm=self.layer_norm,
                noisy_layer=self.noisy_layer,
                output_activation=self.output_activation,
                scope=scope)

    def get_info(self):
        info = {}
        info["architecture"] = "standard"
        info["embedding_layers"] = self.embedding_layers
        info["embedding_activations"] = self.embedding_activations
        info["lstm_layers"] = self.lstm_layers
        info["lstm_activations"] = self.lstm_activations
        info["output_layers"] = self.lstm_layers
        info["output_layers_activations"] = self.lstm_activations
        info["layer_norm"] = self.layer_norm
        info["noisy_layer"] = self.noisy_layer
        info["output_activation"] = self.output_activation
        info["action_insert_block"] = self.act_insert_block
        info["num_atoms"] = self.num_atoms
        return info