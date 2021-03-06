from sklearn.model_selection import train_test_split
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import classification_report
import pandas as pd
from ifn import *
import warnings
warnings.filterwarnings('ignore')


TRAIN_PATH = "../data/processed/train2/"
REF_PATH = "../data/processed/reference/"
WRITE_PATH = "../data/models/"
DF_PATH = "../data/dataframes/"
CLASSIFICATION_THRESHOLD = 0.5
UPPER_CAP = 100
LOWER_CAP = 0.00001
EXPERIMENT_TYPE = 'norm_plot_original_ldc_0.5'
# EXPERIMENT_TYPE = 'ldc_0.7'
# EXPERIMENT_TYPE = 'ldc_0.45'

ref_df = None
temp_df = None

if os.path.exists(DF_PATH) == False:
	os.mkdir(DF_PATH)
	print('Created directory - ', DF_PATH)

if os.path.exists(DF_PATH+'ref_df.pkl') == False:
	ref_df = setup_df(REF_PATH)
	ref_df = get_audio_features(ref_df)
	ref_df.to_pickle(DF_PATH+'ref_df.pkl')
	print('Created file - ', DF_PATH+'ref_df.pkl')
else:
	ref_df = pd.read_pickle(DF_PATH+'ref_df.pkl')
if os.path.exists(DF_PATH+'temp_df.pkl') == False:
	temp_df = setup_df(TRAIN_PATH)
	temp_df.to_pickle(DF_PATH+'temp_df.pkl')
	print('Created file - ', DF_PATH+'temp_df.pkl')
else:
	temp_df = pd.read_pickle(DF_PATH+'temp_df.pkl')


trained_GMMs = get_trained_GMMs(ref_df)
avg_F0_ref = get_avg_F0_ref(ref_df)



def dump_train(to_dump, WRITE_PATH, EXPERIMENT_TYPE):
	with open(WRITE_PATH+EXPERIMENT_TYPE+'.pickle', 'wb') as handle:
		pickle.dump(to_dump, handle, protocol=pickle.HIGHEST_PROTOCOL)

def train_ifn():

	# for every epoch
	epoch = 0

	CLF_REPORT = []
	ITERATION_FILE_CHANGE = []
	LDC_CLFS = []


	for iterations in range(400):

		sampled_df = stratified_sample_df(temp_df)
		
		train_df, test_df = train_test_split(sampled_df, test_size = 0.33, stratify = sampled_df[['speaker','speech_type']])
		
		train_df = get_audio_features(train_df)
		test_df = get_audio_features(test_df)
		
		train_df['F0_contour_sum'] = train_df['F0_contour'].apply(sum)
		train_df['F0_contour_length'] = train_df['F0_contour'].apply(len)

		count = 0

		sampled_df_norm = None
		ldc_clf = None
		epsilon = 1000000
		max_iters = 1000
		
		ldc_clf = LinearDiscriminantAnalysis(solver='lsqr')
		
		print('*************************************************') 
		print('ITERATION NUMBER - ',iterations)
		print('*************************************************') 

		
		ITERATION_CLF_REPORT = []
		ITERATION_FILE_CHANGE_ELEM = []

		while epsilon > 0.05 and count < max_iters:

			for stage in ['train', 'test']:

				print('----------------------------------------')   
				print('Stage - ', stage)
				
				if stage == 'train':
			
					print('=========================================')   
					

					if count ==0 :
						train_df['F0_contour_sum'] = train_df['F0_contour'].apply(sum)
						train_df['F0_contour_length'] = train_df['F0_contour'].apply(len)
						train_df = get_audio_features(train_df, norm=False)
					else:
						train_df['F0_contour_sum'] = train_df['F0_contour_norm'].apply(sum)
						train_df['F0_contour_length'] = train_df['F0_contour_norm'].apply(len)
						# Change above to F0_contour_norm when norm=True
						train_df = get_audio_features(train_df, norm=True)
							
					train_df['inferred'] = train_df.apply(lambda x: infer_GMM(x, trained_GMMs),axis=1)
					
					ldc_clf.fit(np.array(train_df['inferred'].tolist()),train_df['speech_type'].values)

					train_df['predicted_likelihood'] = ldc_clf.predict_proba(np.array(train_df['inferred'].tolist()))[:,0]

					train_df, epsilon = get_stopping_criteria(train_df, count, CLASSIFICATION_THRESHOLD=CLASSIFICATION_THRESHOLD)
					
					print(count)
					print(epsilon)
					ITERATION_FILE_CHANGE_ELEM.append(epsilon)
					LDC_CLFS.append(ldc_clf)
					
					train_df['prev_changed_speech_type'] = train_df['changed_speech_type']
									
					sampled_df_norm, train_df = get_normalised_df(train_df, avg_F0_ref=avg_F0_ref, get_S_s_F0=get_S_s_F0)                
					count+=1

				else:
					sampled_df_test = test_df
					if count!=0:
						_, sampled_df_test = get_normalised_df_infer(test_df, sampled_df_norm)
					if count == 0 :
						sampled_df_test = get_audio_features(sampled_df_test, norm=False)
					else:
						sampled_df_test = get_audio_features(sampled_df_test, norm=True)
					sampled_df_test['inferred'] = sampled_df_test.apply(lambda x: infer_GMM(x, trained_GMMs),axis=1)

					sampled_df_test['predicted_likelihood'] = ldc_clf.predict_proba(np.array(sampled_df_test['inferred'].tolist()))[:,0]

					sampled_df_test = get_pred_labels(sampled_df_test, CLASSIFICATION_THRESHOLD=CLASSIFICATION_THRESHOLD)

					clf_report = classification_report(sampled_df_test['speech_type'],sampled_df_test['changed_speech_type'], output_dict=True)
					ITERATION_CLF_REPORT.append(clf_report)
					print(clf_report)

		ITERATION_FILE_CHANGE.append(ITERATION_FILE_CHANGE_ELEM)
		CLF_REPORT.append(ITERATION_CLF_REPORT)
					
					

	to_dump = {'clf_report':CLF_REPORT, 'file_change':ITERATION_FILE_CHANGE, 'ldc_clfs':LDC_CLFS, 'gmms': trained_GMMs}

	return to_dump



if __name__ == "__main__":

	to_dump = train_ifn()
	dump_train(to_dump, WRITE_PATH, EXPERIMENT_TYPE)
	print('------------------COMPLETE------------------')








