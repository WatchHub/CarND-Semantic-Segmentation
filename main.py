import os.path
import tensorflow as tf
import helper
import warnings
from distutils.version import LooseVersion
import project_tests as tests

# Check TensorFlow Version
assert LooseVersion(tf.__version__) >= LooseVersion(
    '1.0'), 'Please use TensorFlow version 1.0 or newer.  You are using {}'.format(tf.__version__)
print('TensorFlow Version: {}'.format(tf.__version__))

# Check for a GPU
if not tf.test.gpu_device_name():
    warnings.warn(
        'No GPU found. Please use a GPU to train your neural network.')
else:
    print('Default GPU Device: {}'.format(tf.test.gpu_device_name()))


def load_vgg(sess, vgg_path):
    """
    Load Pretrained VGG Model into TensorFlow.
    :param sess: TensorFlow Session
    :param vgg_path: Path to vgg folder, containing "variables/" and "saved_model.pb"
    :return: Tuple of Tensors from VGG model (image_input, keep_prob, layer3_out, layer4_out, layer7_out)
    """
    #   Use tf.saved_model.loader.load to load the model and weights
    vgg_tag = 'vgg16'
    vgg_input_tensor_name = 'image_input:0'
    vgg_keep_prob_tensor_name = 'keep_prob:0'
    vgg_layer3_out_tensor_name = 'layer3_out:0'
    vgg_layer4_out_tensor_name = 'layer4_out:0'
    vgg_layer7_out_tensor_name = 'layer7_out:0'

    tf.saved_model.loader.load(sess, [vgg_tag], vgg_path)
    graph = tf.get_default_graph()
    image_input = graph.get_tensor_by_name(vgg_input_tensor_name)
    keep_prob = graph.get_tensor_by_name(vgg_keep_prob_tensor_name)
    layer3_out = graph.get_tensor_by_name(vgg_layer3_out_tensor_name)
    layer4_out = graph.get_tensor_by_name(vgg_layer4_out_tensor_name)
    layer7_out = graph.get_tensor_by_name(vgg_layer7_out_tensor_name)

    return image_input, keep_prob, layer3_out, layer4_out, layer7_out


tests.test_load_vgg(load_vgg, tf)


def layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes):
    """
    Create the layers for a fully convolutional network.  Build skip-layers using the vgg layers.
    :param vgg_layer3_out: TF Tensor for VGG Layer 3 tensor
    :param vgg_layer4_out: TF Tensor for VGG Layer 4 tensor
    :param vgg_layer7_out: TF Tensor for VGG Layer 7 tensor
    :param num_classes: Number of classes to classify
    :return: The Tensor for the last layer of tensor
    """
    regularizer = tf.contrib.layers.l2_regularizer(1e-3)
    conv_1x1_l3 = tf.layers.conv2d(vgg_layer3_out, num_classes, 1, padding='same',
                                   kernel_regularizer=regularizer)
    conv_1x1_l4 = tf.layers.conv2d(vgg_layer4_out, num_classes, 1, padding='same',
                                   kernel_regularizer=regularizer)
    conv_1x1_l7 = tf.layers.conv2d(vgg_layer7_out, num_classes, 1, padding='same',
                                   kernel_regularizer=regularizer)

    tensor = tf.layers.conv2d_transpose(
        conv_1x1_l7, num_classes, 4, strides=(2, 2), padding='same', kernel_regularizer=regularizer)
    tensor = tf.add(tensor, conv_1x1_l4)
    tensor = tf.layers.conv2d_transpose(
        tensor, num_classes, 4, strides=(2, 2), padding='same', kernel_regularizer=regularizer)
    tensor = tf.add(tensor, conv_1x1_l3)
    tensor = tf.layers.conv2d_transpose(
        tensor, num_classes, 16, strides=(8, 8), padding='same', kernel_regularizer=regularizer)

    return tensor


tests.test_layers(layers)


def optimize(nn_last_layer, correct_label, learning_rate, num_classes):
    """
    Build the TensorFLow loss and optimizer operations.
    :param nn_last_layer: TF Tensor of the last layer in the neural network
    :param correct_label: TF Placeholder for the correct label image
    :param learning_rate: TF Placeholder for the learning rate
    :param num_classes: Number of classes to classify
    :return: Tuple of (logits, train_op, cross_entropy_loss)
    """
    logits = tf.reshape(nn_last_layer, (-1, num_classes))
    labels = tf.reshape(correct_label, (-1, num_classes))

    cross_entropy_loss = tf.reduce_mean(
        tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=labels))

    optimizer = tf.train.AdamOptimizer(learning_rate)
    train_op = optimizer.minimize(cross_entropy_loss)

    return logits, train_op, cross_entropy_loss


tests.test_optimize(optimize)


def train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, input_image,
             correct_label, keep_prob, learning_rate):
    """
    Train neural network and print out the loss during training.
    :param sess: TF Session
    :param epochs: Number of epochs
    :param batch_size: Batch size
    :param get_batches_fn: Function to get batches of training data.  Call using get_batches_fn(batch_size)
    :param train_op: TF Operation to train the neural network
    :param cross_entropy_loss: TF Tensor for the amount of loss
    :param input_image: TF Placeholder for input images
    :param correct_label: TF Placeholder for label images
    :param keep_prob: TF Placeholder for dropout keep probability
    :param learning_rate: TF Placeholder for learning rate
    """
    for e in range(epochs):
        for i, (image, label) in enumerate(get_batches_fn(batch_size)):
            _, loss = sess.run(
                [train_op, cross_entropy_loss], feed_dict={input_image: image, correct_label: label,
                                                           keep_prob: 0.5, learning_rate: 1e-4})
            print('Epoch: {} batch: {} loss: {:.3f}'.format(e + 1, i + 1, loss))


tests.test_train_nn(train_nn)


def run():
    batches = 2
    epochs = 80
    save_model = True
    restore_model = True
    inferance_only = False
    compute_iou = True

    num_classes = 2
    image_shape = (160, 576)
    data_dir = './data'
    runs_dir = './runs'
    tests.test_for_kitti_dataset(data_dir)

    # Download pretrained vgg model
    helper.maybe_download_pretrained_vgg(data_dir)

    with tf.Session() as sess:
        correct_label = tf.placeholder(
            tf.int32, [None, None, None, num_classes])
        learning_rate = tf.placeholder(tf.float32)

        # Path to vgg model
        vgg_path = os.path.join(data_dir, 'vgg')
        # Create function to get batches
        get_batches_fn = helper.gen_batch_function(
            os.path.join(data_dir, 'data_road/training'), image_shape)

        input_image, keep_prob, layer3_out, layer4_out, layer7_out = load_vgg(
            sess, vgg_path)
        tensor = layers(layer3_out, layer4_out, layer7_out, num_classes)
        logits, optimizer, cross_entropy_loss = optimize(tensor, correct_label, learning_rate,
                                                         num_classes)

        if compute_iou:
            predictions = tf.argmax(tf.nn.softmax(tensor), axis=-1)
            gt = tf.argmax(correct_label, axis=-1)
            mean_iou, iou_update_op = tf.metrics.mean_iou(
                gt, predictions, num_classes)

        sess.run(tf.global_variables_initializer())
        sess.run(tf.local_variables_initializer())

        saver = tf.train.Saver()
        restore_path = tf.train.latest_checkpoint('./ckpts/')
        if restore_path and restore_model:
            print("Resotring model from: %s " % restore_path)
            saver.restore(sess, restore_path)

        if not inferance_only:
            train_nn(sess, epochs, batches, get_batches_fn, optimizer, cross_entropy_loss, input_image,
                     correct_label, keep_prob, learning_rate)

        #compute mean_iou on traning images
        if compute_iou:
            print("Computing IOU...")
            mean_ious = []
            for image, label in (get_batches_fn(batches)):
                sess.run([predictions, iou_update_op], feed_dict={
                    input_image: image, correct_label: label, keep_prob: 1})
                # Avoiding headaches
                # http://ronny.rest/blog/post_2017_09_11_tf_metrics/
                mean_ious.append(sess.run(mean_iou))
            print("Mean IOU: {:.3f}".format(sum(mean_ious) / len(mean_ious)))

        if save_model:
            save_path = saver.save(sess, "./ckpts/model.ckpt")
            print("Model saved in path: %s" % save_path)

        helper.save_inference_samples(
            runs_dir, data_dir, sess, image_shape, logits, keep_prob, input_image)


if __name__ == '__main__':
    run()
